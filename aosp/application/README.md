# Application 

## Activity 启动整体流程


<img src="aosp/application/resources/app_1.png" style="width:100%"/>

1. 用户点击 App 图标，Launcher 进程启动目标 Activity
2. SystemServer 中的 AMS/ATMS 收到请求，创建对应的 ActivityRecord 和 Task，并挂载到窗口层级树中
3. AMS/ATMS pause 源 Activity
4. 源 Activity pause 完成后，告知 AMS/ATMS pause 过程完成，AMS/ATMS 通知到 Zygote 创建新进程
5. 目标 App 进程启动后，向 AMS/ATMS attach 当前进程信息
6. AMS/ATMS 远程调用到 app ，app 初始化 Application，执行 onCreate 生命周期方法，初始化 Activity，执行 onCreate OnResume 等生命周期方法