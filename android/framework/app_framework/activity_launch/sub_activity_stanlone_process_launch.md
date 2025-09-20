# 子 Activity 组件在独立进程内的启动过程

结合 MainActivity 组件和 SubActivityInProcess 组件的启动过程，我们就可以得到 SubActivityInNewProcess 组件的启动过程，如下所示。

1. MainActivity 组件向 AMS 发送一个启动 SubActivityInNewProcess 组件的进程间通信请求。
2. AMS 首先将要启动的 SubActivityInNewProcess 组件的信息保存下来，然后再向 MainActivity 组件发送一个进入中止状态的进程间通信请求。
3. MainActivity 组件进入到中止状态之后，就会向 AMS 发送一个已进入中止状态的进程间通信请求，以便 AMS 可以继续执行启动 SubActivityInNewProcess 组件的操作。
4. AMS 发现用来运行 SubActivityInNewProcess 组件的应用程序进程不存在，因此它就会先启动一个新的应用程序进程。
5. 新的应用程序进程启动完成之后，就会向 AMS 发送一个启动完成的进程间通信请求，以便 AMS 可以继续执行启动 SubActivityInNewProcess 组件的操作。
6. AMS 将第 2 步保存下来的 SubActivityInNewProcess 组件信息发送给第 4 步创建的应用程序进程，以便它可以将 SubActivityInNewProcess 组件启动起来。