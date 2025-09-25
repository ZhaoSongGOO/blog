# Android 系统广播

在 Android 系统中，广播(Broadcast)是一种在组件之间进行消息传递的方式。这些组件可以运行在同一个进程中，也可以运行在不同的进程中。当两个不在同一个进程中的组件通过广播机制来传递消息时，广播机制就有点类似 Binder 进程间通信机制。事实上，广播机制就是在 Binder 进程间通信机制的基础上实现的。

既然如此，Android 系统为什么还需要提供广播机制呢?我们知道，在 Binder 进程间通信机制中，Client 组件在和 Service 组件通信之前，必须要先获得它的一个代理对象，即 Client 组件事先要知道 Service 组件的存在。然而，在广播机制中，广播发送者事先是不需要知道广播接收者的存在的，这样就可以降低广播发送者和广播接收者之间的耦合度，进而提高系统的可扩展性和可维护性。因此，Android 系统需要提供广播机制。

广播机制是一种基于消息发布和订阅的事件驱动模型，即广播发送者负责发布消息，而广播接收者需要先订阅消息，然后才能接收到消息。Android 系统将广播接收者抽象为一种 Broadcast Receiver 组件，它是 Android 应用程序的四大组件之一。同时，Android 应用程序的另外两种组件，即 Activity 组件和 Service 组件被赋予了发送广播的能力。因此，在 Android 系统中，使用广播机制在组件之间传递消息是非常方便的。

广播机制存在一个注册中心，它是由 ActivityManagerService 来担当的。广播接收者订阅消息的表现形式就是将自己注册到 ActivityManagerService 中，并且指定要接收的广播的类型。当广播发送者向广播接收者发送一个广播时，这个广播首先发送到 ActivityManagerService，然后 ActivityManagerService 根据这个广播的类型找到相应的广播接收者，最后将这个广播发送给它们处理。

广播接收者的注册方式分为静态注册和动态注册两种。在静态注册方式中，用来描述广播接收者的 Broadcast Receiver 组件必须要在配置文件 AndroidManifest.xml 中注明它们所感兴趣的广播的类型，以便 ActivityManagerService 可以找到它们。在动态注册方式中，我们需要在代码中手动地调用 Context 接口的成员函数 registerReceiver 将 Broadcast Receiver 组件注册到 ActivityManagerService 中。Activity 组件和 Service 组件都实现了 Context 接口，因此，我们可以方便地在一个 Activity 组件或者 Service 组件中注册一个 Broadcast Receiver 组件。在同等情况下，动态注册的广播接收者要比静态注册的广播接收者优先接收到广播。

广播的发送方式分为有序和无序两种。我们在注册广播接收者时，可以指定它们的优先级。当 ActivityManagerService 接收到有序广播时，它就会先将这个有序广播发送给符合条件的、优先级较高的广播接收者处理，然后再发送给符合条件的、优先级较低的广播接收者处理；而当 ActivityManagerService 接收到无序广播时，它就会忽略广播接收者的优先级，并行地将这个无序广播发送给所有符合条件的广播接收者处理。

## [广播接收者的注册](android/framework/app_framework/broadcast/receiver_register.md)