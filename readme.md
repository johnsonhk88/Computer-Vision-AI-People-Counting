# Computer Vision AI People Counting

### Introductions

### Business Use case
Something, we need know how many people visit specific place in specific place. such as shopping Mall, Public area, country park. This statistic data can help business for make accuray decision how to allocate , manage people flow in specific , as well as good promotion event time rearragement.

Tradition, we need manual spend staff to  count how many people in specific place at specific people. The data possible some counting error and spend a lot of resource to arrange the counting. 

This project  used AI computer vision Model to automatically count the people at 24hours , not limit the specific place and time. 

### Technology use in this project
1. Computer vision: 
- this project used ip-camera base as video source to recognize the people  

2. AI Real Time Model
- Use Yolo Real time Object detection model for reconize the people 
- Use Object Tracking model like StrongSORT for tracking the people flow direction 
- OpenCV to control and extract the raw image from ipcam , sent to AI model.

3. Database
- use SQL database store history data for future data analysis use.


### Run Application
- there are several sample code can use for testing , select different folder