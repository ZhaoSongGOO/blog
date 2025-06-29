# Core

## Activity, DecorView, ViewRootImpl, Window 关系

<img src="android/interview/core/resources/2.png" style="width:100%">

我们首先列举出这几个对象之间的 UML 图，下面会通过几个阶段来解释这个 UML 的形成过程。

<img src="android/interview/core/resources/3.png" style="width:100%">

### Attach 阶段

当系统创建 `Activity` 的时候，会触发 `attach` 方法，这个方法会初始化 `PhoneWindow`，并同时把自己作为 `Window.Callback` 注册给 `PhoneWindow`。 `attach` 这函数最后阶段会触发 `Activity` 的 `onCreate` 回调。

在这一阶段结束后，`Activity` 直接持有了 `PhoneWindow`, `PhoneWindow` 以回调的方式持有了 `Activity`。


### setContentView 阶段

我们自定义的 `Activity` 一般需要在 `onCreate` 回调中调用 `setContentView` 方法来初始化视图。 `Activity` 的 `setContentView` 直接调用 `PhoneWindow` 的 `setContentView` 方法。在 `PhoneWindow` 中，如果发现还没有创建 `DecorView`, 那就创建 `DecorView`，并将屏幕根视图挂载成其直接子节点，同时将传入的 layout 资源挂载在 屏幕根视图的 `content` 容器中。

换句话说，你写的 activity.xml 只是 activity 视图树的一部分。

<img src="android/interview/core/resources/1.png" style="width:20%">

经过这一阶段，`PhoneWindow` 创建并持有了 `DecorView`, 同时 `DecorView` 通过 setWindow 接口持有了 `PhoneWindow`。

### 可见阶段

系统会在某个时机触发 `Activity` 的 `onResume` 方法，代表整个视图将要进入可见状态，执行完 `onResume` 后，系统认为你 `Activity` 的状态已经准备好，就调用到 `Activity` 的 `MakeVisiable` 方法。`MakeVisiable` 直接通过持有的 `PhoneWindow` 拿到 `WindowManager`，并进而通过 `WindowManager` 调用 `WindowManagerImpl`，然后会在一个全局单例的 `WindowManagerGlobal` 对象中创建 `ViewRootImpl` 对象。并通过其 `setView` 方法将 `DecorView` 绑定到 `ViewRootImpl` 上。需要注意的是 `WindowManagerGlobal` 持有了所有的 `DecorView` 以及 `ViewRootImpl` 实例。

经过这个阶段，创建了 `ViewRootImpl` 对象，并将 `DecorView` 绑定在其上。

### dispatchAttachedToWindow 阶段

随着 `VSync` 的到来，触发 `ViewRootImpl` 注册的回调，这个回调会执行 `performTraversal` 方法，这个方法中进行判断，如果是第一次执行绘制就会进行 `attachToWindow` 的操作。这里 `host` 就是 上一步绑定给 `ViewRootImpl` 的 `DecorView。` `ViewRootImpl` 在执行这个方法的时候，会把自己保存在 `mAttachInfo` 一并传入，在 `DecorView` 的 `dispatchAttachedToWindow` 中就可以通过 mAttachInfo 间接获取到 `ViewRootImpl` 了。

```java
// ViewRootImpl.java
host.dispatchAttachedToWindow(mAttachInfo, 0);
```

通过这一步，`DecorView` 可以访问到 `ViewRootImpl`了！


## Context 是什么？


## 深入理解 Activity

### 什么是 Activity？

Activity 是 Android 应用中的一个组件（Component），用于承载和管理用户界面（UI）以及与用户的交互。每个 Activity 通常对应一个用户可以看到和操作的界面，比如登录页、主页面、设置页等。

其主要作用如下：
- 管理应用的窗口和界面布局。
- 响应用户的输入（比如点击、滑动等）。
- 启动其他 Activity 或与其他应用进行交互。

### Activity 类结构

<img src="android/interview/core/resources/4.png" style="width:20%">

Activity 继承自 Context，同时实现了一系列的接口。

Activity 中持有了对 PhoneWindow、Application、ActivityThread、Instrumentation 等关键对象的引用，这些引用一般是在 attach 函数被调用的时候传入的。

### Activity 创建流程

<img src="android/interview/core/resources/5.png" style="width:100%">

我们下面以一个应用完全启动的流程为例来讲解 Activity 创建的流程。

1. 用户点击桌面的 APP 图标

所谓的手机桌面本身也是一个应用，桌面的图标不过是一些 Button 而已，而这些 Button 对于点击事件的响应恰好是打开对应的应用，因此当你点击了某个 APP icon 的时候，实际上是在桌面应用中调用了 startActivity 方法。那 startActivity 的目标是哪个 Activity 呢？ 就是你在 AndroidManife 文件中指定的 launch activity。

2. 发送 Activity 创建消息

桌面应用 startActivity 会通过底层 binder 驱动将启动消息发送给 ATMS 服务。ATMS 是一个运行在独立进程的系统服务。ATMS 收到这个请求后，首先进行一些权限检查，如果没有通过权限检查就会启动失败，并抛出异常。如果权限校验通过，就会去判断 Activity 所在的应用是不是已经存在了，如果存在，就直接通过 binder 触发对应 APP 进程的 ApplicationThread proxy。让他执行 activity 创建工作。

如果对应的 APP 不存在，
- 会首先将本次启动 Activity 的信息存储起来，随后触发 zygote 创建对应的应用。在触发后，ATMS 不会阻塞，而是转头去接受其他的请求。
- zygote fork 新的 app 进程，并通过反射调用 ActiviyThread.main 方法。
- ActiviyThread.main 会通过 binder 告诉 ATMS，APP 已经创建好了。
- ATMS 收到消息后，从刚才缓存的信息中拿出需要启动的 Activity 信息，并通过 binder 触发 ApplicationThread 的 handlerLaunchActivity 方法，这个方法中会创建 Context、Applcation 对象以及 activity 对象。并将 activity.attach(context, application,...) 等信息关联起来。随后调用 activity.onCreate 方法。
- ATMS 会在合适的时候，通过 binder 触发 ApplicationThread 的 handlerStartActivity、handlerResumeActivity 等方法来触发 activity 对应的生命周期回调。


上面多次提到了 ActivityThread 和 ApplicationThread, 其两者的关系如下：
1. ApplicationThread 是 ActivityThread 的内部类，其实现了 binder 接口，用于和 ATMS 进行通信。
2. ApplicationThread 收到 ATMS 的消息后，会使用 sendMessage 触发 ActivityThread 对应的方法。

<img src="android/interview/core/resources/6.png" style="width:30%">


## 深入理解 Window

## 深入理解 Service

这里的 Service 是 Android 系统四大组件之一的 Service，和上面提到的 ATMS 有本质的区别，具体差别如下：

<img src="android/interview/core/resources/7.png" style="width:60%">

### Service 启动停止流程分析

#### startService & stopService
当我们在 context 的上下文中，就可以使用 context.startService 方法来启动一个服务。具体的流程其实和启动 Activity 非常类似。

1. context.startService 通过 binder 给 AMS 发送启动服务请求。
2. AMS 收到请求后，经过一些判断后，通过 binder 发送消息到 ApplicationThread， ApplicationThread 进一步调用 ActivityThread 的 handleCreateService 方法。
3. handleCreateService 中创建对应的 Service，随后调用其 service.onCreate 方法。创建完成后，再通过 binder 通知 AMS，service 已经创建好了。
4. AMS 收到 service 创建完成的信号后，会再一次通过 binder 发送消息到 ApplicationThread，并进一步触发 ActivityThread 的 handleServiceArgs 方法。
5. 在 handleServiceArgs 中，会调用 service.onStartCommand 方法。
6. 至此，service 创建完成。

7. 如果后续调用 stopService。同样的通过 binder 发送到 AMS，AMS 做判断后会使用 binder 发送消息到 ApplicationThread，并进一步触发 ActivityThread 的 handleStopService 方法。
8. 在 handleStopService 中会调用 service.onDestory 方法。

#### bindSevice & unbindService

与普通的 start 和 stop 不同，bind 会返回一个 IBinder 对象，用户可以通过这个 IBinder 对象来与 service 进行通信。

1. context.bindService 通过 binder 给 AMS 发送绑定服务请求。
2. AMS 如果发现 service 没有创建会和之前一样 先 binder 调用 ActivityThread 的 handleCreateService 方法。
3. AMS 收到 service 创建完成的信号后，会再一次通过 binder 发送消息到 ApplicationThread，并进一步触发 ActivityThread 的 handleBindService 方法。
4. handleBindService 会返回 IBinder 对象给 AMS。
5. AMS 把这个对象返回给客户端。
6. 客户端如果和 Service 一个进程，这个 IBinder 就是本地对象，无 IPC 开销。如果是其余进程，那 IBinder 后续基于 binder 做通信。


## 深入理解 BroadCast

## 深入理解 ContentProvider