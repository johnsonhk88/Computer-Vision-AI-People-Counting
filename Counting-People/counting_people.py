# Usage example:  python3 counting_people.py --video=TownCentreXVID.avi

from tkinter import Y
import cv2 as cv
import argparse
import sys
import numpy as np
import os.path
import math
from counting.centroidtracker import CentroidTracker
from counting.trackableobject import TrackableObject

# Initialize the parameters
# YoloV3 setting
confThreshold = 0.6  #Confidence threshold
nmsThreshold = 0.4   #Non-maximum suppression threshold
inpWidth = 416       #Width of network's input image
inpHeight = 416      #Height of network's input image

parser = argparse.ArgumentParser(description='Object Detection using YOLO in OPENCV')

parser.add_argument('--video', help='Path to video file.')
parser.add_argument("--ipcamAddr", nargs="?", type=str, default="")
parser.add_argument("--resize", nargs="?", type=float, default=1.0)
parser.add_argument("--device", nargs="?", type=str, default="cpu")
parser.add_argument("--upCount", nargs="?", type=int, default=0)
parser.add_argument("--downCount", nargs="?", type=int, default=0)
parser.add_argument("--model", nargs="?", type=str, default="yolov4")
parser.add_argument("--objectClass", nargs="?", type=int, default=0) # CoCo dataset id define for object detection, default 0 = people

args = parser.parse_args()
        
# Load names of classes
classesFile = "coco.names";
classes = None
with open(classesFile, 'rt') as f:
    classes = f.read().rstrip('\n').split('\n')

yoloModel = args.model#"yolov4" #,"yolov4-tiny" , "yolov3" 

# Give the configuration and weight files for the model and load the network using them.
if yoloModel == "yolov4":
    modelConfiguration = "yolov4.cfg"#"yolov3-spp.cfg";
    modelWeights = "yolov4.weights"#"yolov3-spp.weights";
    print("Yolov4")
elif yoloModel == "yolov4-tiny":
    modelConfiguration = "yolov4-tiny.cfg"#"yolov3-spp.cfg";
    modelWeights = "yolov4-tiny.weights"#"yolov3-spp.weights";
    print("Yolov4-Tiny")
else:
    modelConfiguration = "yolov3-spp.cfg";
    modelWeights = "yolov3-spp.weights";
    print("Yolov3")


# load our serialized model from disk
print("[INFO] loading model...")
net = cv.dnn.readNetFromDarknet(modelConfiguration, modelWeights)
#for origin 
# net.setPreferableBackend(cv.dnn.DNN_BACKEND_OPENCV)
# net.setPreferableTarget(cv.dnn.DNN_TARGET_OPENCL)
if args.device == "gpu":
    #for CUDA gpu 
    net.setPreferableTarget(cv.dnn.DNN_TARGET_CUDA)
    net.setPreferableBackend(cv.dnn.DNN_BACKEND_CUDA)
elif args.device == "cpu":
    #for CPU
    net.setPreferableBackend(cv.dnn.DNN_BACKEND_OPENCV)
    net.setPreferableTarget(cv.dnn.DNN_TARGET_CPU)

# initialize the video writer
writer = None
 
# initialize the frame dimensions (we'll set them as soon as we read
# the first frame from the video)
W = None
H = None
 
# instantiate our centroid tracker, then initialize a list to store
# each of our dlib correlation trackers, followed by a dictionary to
# map each unique object ID to a TrackableObject
ct = CentroidTracker(maxDisappeared=40, maxDistance=50)
trackers = []
trackableObjects = {}
 
# initialize the total number of frames processed thus far, along
# with the total number of objects that have moved either up or down
totalDown = args.downCount
totalUp = args.upCount

# Get the names of the output layers
def getOutputsNames(net):
    # Get the names of all the layers in the network
    layersNames = net.getLayerNames()
    # print("num of layer name: ", len(layersNames), " ",type(layersNames))
    # print("layersName: ",layersNames)
    # Get the names of the output layers, i.e. the layers with unconnected outputs
    # return [layersNames[i[0] - 1] for i in net.getUnconnectedOutLayers()]
    return [layersNames[int(i) - 1] for i in net.getUnconnectedOutLayers()]
    # return layersNames

# Draw the predicted bounding box
def drawPred(classId, conf, left, top, right, bottom):
    # Draw a bounding box.
    # cv.rectangle(frame, (left, top), (right, bottom), (255, 178, 50), 2)
    # Draw a center of a bounding box
    frameHeight = frame.shape[0]
    frameWidth = frame.shape[1]
    cv.line(frame, (0, frameHeight//2 - 50), (frameWidth, frameHeight//2 - 50), (0, 255, 255), 2)
    cv.circle(frame,(left+(right-left)//2, top+(bottom-top)//2), 3, (0,0,255), -1)
        

    counter = []
    if (top+(bottom-top)//2 in range(frameHeight//2 - 2,frameHeight//2 + 2)):
        coun +=1
        #print(coun)

        counter.append(coun)

    label = 'Pedestrians: '.format(str(counter))
    cv.putText(frame, label, (0, 30), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255))


def showPeopleCount(frame):
    info = [
        ("Up", totalUp),
        ("Down", totalDown),
    ]

    # loop over the info tuples and draw them on our frame
    for (i, (k, v)) in enumerate(info):
        text = "{}: {}".format(k, v)
        cv.putText(frame, text, (10, frameHeight - ((i * 20) + 20)),
            cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)


# Remove the bounding boxes with low confidence using non-maxima suppression
def postprocess(frame, outs , objectClass):
    frameHeight = frame.shape[0]
    frameWidth = frame.shape[1]

    rects = []

    # Scan through all the bounding boxes output from the network and keep only the
    # ones with high confidence scores. Assign the box's class label as the class with the highest score.
    classIds = []
    confidences = []
    boxes = []
    for out in outs:
        for detection in out:
            scores = detection[5:]
            classId = np.argmax(scores)
            confidence = scores[classId]
            if confidence > confThreshold:
                center_x = int(detection[0] * frameWidth)
                center_y = int(detection[1] * frameHeight)
                width = int(detection[2] * frameWidth)
                height = int(detection[3] * frameHeight)
                left = int(center_x - width / 2)
                top = int(center_y - height / 2)
                classIds.append(classId)
                confidences.append(float(confidence))
                boxes.append([left, top, width, height])

    # Perform non maximum suppression to eliminate redundant overlapping boxes with
    # lower confidences.
    indices = cv.dnn.NMSBoxes(boxes, confidences, confThreshold, nmsThreshold)
    # print("indices: ", indices, " ", type(indices))
    for i in indices:
        # print("i value: ", i)
        # i = i[0]
        box = boxes[i]
        left = box[0]
        top = box[1]
        width = box[2]
        height = box[3]
        # Class "person"
        if classIds[i] == objectClass: # check object class id is 0 for person
            rects.append((left, top, left + width, top + height))
            # use the centroid tracker to associate the (1) old object
            # centroids with (2) the newly computed object centroids
            objects = ct.update(rects)
            counting(objects)

            #drawPred(classIds[i], confidences[i], left, top, left + width, top + height)

def counting(objects):
    frameHeight = frame.shape[0]
    frameWidth = frame.shape[1]

    global totalDown
    global totalUp

    # loop over the tracked objects
    for (objectID, centroid) in objects.items():
        # check to see if a trackable object exists for the current
        # object ID
        to = trackableObjects.get(objectID, None)
 
        # if there is no existing trackable object, create one
        if to is None:
            to = TrackableObject(objectID, centroid)
 
        # otherwise, there is a trackable object so we can utilize it
        # to determine direction
        else:
            # the difference between the y-coordinate of the *current*
            # centroid and the mean of *previous* centroids will tell
            # us in which direction the object is moving (negative for
            # 'up' and positive for 'down')
            y = [c[1] for c in to.centroids]
            direction = centroid[1] - np.mean(y)
            to.centroids.append(centroid)
 
            # check to see if the object has been counted or not
            if not to.counted:
                # if the direction is negative (indicating the object
                # is moving up) AND the centroid is above the center
                # line, count the object

                if direction < 0 and centroid[1] in range(frameHeight//2 - 30, frameHeight//2 + 30):
                    totalUp += 1
                    to.counted = True
 
                # if the direction is positive (indicating the object
                # is moving down) AND the centroid is below the
                # center line, count the object
                elif direction > 0 and centroid[1] in range(frameHeight//2 - 30, frameHeight//2 + 30):
                    totalDown += 1
                    to.counted = True
 
        # store the trackable object in our dictionary
        trackableObjects[objectID] = to
        # draw both the ID of the object and the centroid of the
        # object on the output frame
        #text = "ID {}".format(objectID)
        #cv.putText(frame, text, (centroid[0] - 10, centroid[1] - 10),
            #cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        cv.circle(frame, (centroid[0], centroid[1]), 4, (0, 255, 0), -1)
    # construct a tuple of information we will be displaying on the
    # frame
    info = [
        ("Up", totalUp),
        ("Down", totalDown),
    ]

    # loop over the info tuples and draw them on our frame
    for (i, (k, v)) in enumerate(info):
        text = "{}: {}".format(k, v)
        cv.putText(frame, text, (10, frameHeight - ((i * 20) + 20)),
            cv.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

# Process inputs
winName = 'Deep learning object detection in OpenCV'
cv.namedWindow(winName, cv.WINDOW_NORMAL)

outputFile = "yolo_out_py.avi"

if (args.video):
    # Open the video file
    if not os.path.isfile(args.video):
        print("Input video file ", args.video, " doesn't exist")
        sys.exit(1)
    cap = cv.VideoCapture(args.video)
    outputFile = args.video[:-4]+'_yolo_out_py.avi'
elif (args.ipcamAddr):
    cap = cv.VideoCapture(args.ipcamAddr)

else:
    # Webcam input
    cap = cv.VideoCapture(0)

# Get the video writer initialized to save the output video
vid_writer = cv.VideoWriter(outputFile, cv.VideoWriter_fourcc('M','J','P','G'), 30, (round(cap.get(cv.CAP_PROP_FRAME_WIDTH)),round(cap.get(cv.CAP_PROP_FRAME_HEIGHT))))

while cv.waitKey(1) < 0:
    
    # get frame from the video
    hasFrame, frame = cap.read()
    
    if hasFrame == False:
        continue

    if args.resize != 1.0:
        frame = cv.resize(frame, None, fx=args.resize, fy=args.resize, interpolation=cv.INTER_AREA)
    frameHeight = frame.shape[0]
    frameWidth = frame.shape[1]
    cv.line(frame, (0, frameHeight // 2), (frameWidth, frameHeight // 2), (0, 255, 255), 2)
    
    # Stop the program if reached end of video
    if not hasFrame:
        print("Done processing !!!")
        print("Output file is stored as ", outputFile)
        cv.waitKey(3000)
        # Release device
        cap.release()
        break

    # Create a 4D blob from a frame.
    blob = cv.dnn.blobFromImage(frame, 1/255, (inpWidth, inpHeight), [0,0,0], 1, crop=False)

    # Sets the input to the network
    net.setInput(blob)

    # Runs the forward pass to get output of the output layers
    outs = net.forward(getOutputsNames(net))

    # Remove the bounding boxes with low confidence
    postprocess(frame, outs , args.objectClass)

    # Put efficiency information. The function getPerfProfile returns the overall time for inference(t) and the timings for each of the layers(in layersTimes)
    t, _ = net.getPerfProfile()
    label = 'Inference time: %.2f ms' % (t * 1000.0 / cv.getTickFrequency())
    cv.putText(frame, label, (0, 15), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255))

    showPeopleCount(frame=frame)
    # Write the frame with the detection boxes

    vid_writer.write(frame.astype(np.uint8))

    cv.imshow(winName, frame)

cap.release()
