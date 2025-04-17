# Scenario Analysis

在 Android 系统中，一套完整的 binder 机制包含四个部分：client、server、server-manager、binder-driver。其中 binder-driver 和 server-manager 是通信的基础，需要预创建。而 client 和 server 则依托于预创建的模块选择合适的时机进行创建。创建整体流程如下：

1. kernel 创建内核进程 swapper，该进程加载 binder-driver。
2. 系统初始化的 init 进程创建一系列的守护进程，其中就包括 server-manager。
3. server 发送注册服务消息到 server-manager。
4. client 获取 server handler。
5. client 触发消息，server 收到后处理消息。



