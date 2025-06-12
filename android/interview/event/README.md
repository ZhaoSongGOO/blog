# Event


## 事件生成

当我们点击手机屏幕的时候，就会生成一个事件，那这个事件是如何生成的呢？

### 硬件层

当用户点击屏幕时，触摸屏控制器生成原始信号，这个信号会包含触摸点坐标、压力等原始信息，并通过总线发送给 设备驱动。

### 内核层

设备驱动 `/dev/input` 收到原始信号后，会进行噪声过滤，并将传入的原始信息封装成 `input_event` 结构体。

### Native 层

在 c++ 层会有一个 `EventHub` 服务，这个服务会监听 `/dev/input`, 并将写入其中的 `input_event` 按照 Android 标准事件格式进行转换。随后使用 `InputDispatcher` 服务借助于 `InputChannel` 发送到应用框架层的 `ViewRootImpl`。



#### ViewRootImpl 如何和 Native 进行事件通信。

简单的描述这个过程就是：整个事件发送过程是一个本地 Socket 通信，Native 层会在合适的时机创建一堆 socket fd，就是 `InputChannel[2]`, 这里面 InputChannel[0] 是服务端 socket fd， 由 `InputDispatcher` 持有。InputChannel[1] 是客户端 socket fd 由 ViewRootImpl 存储。而 ViewRootImpl 和 Native 之间点击事件发送就是通过这两个 socket 来进行的。

这是简单的描述，实际上，unix socket 并不能跨语言通信，所以这里面还有很多的 jni 适配层。下面会进行一个整体的较为详尽的代码分析。

下面这张图展示了点击事件过程中我们关注的几个核心对象的类结构。

- `ViewRootImpl` 与 `DecorView` 关联的时候会通过 JNI 调用触发 `InputChannel` 创建，这个对象保存着客户端 socket fd。
- `ViewRootImpl` 持有了 `InputChannel` 对象。
- `ViewRootImpl` 持有了 `WindowInputEventReceiver`, 这个对象会在构造的时候，通过 JNI 将 `ViewRootImpl` 的 `InputChannel` 和自身传递到 c++ 对象 `NativeInputEventReceiver` 对象中。
- `NativeInputEventReceiver` 会从传入的 `InputChannel` 拿到 client fd，并使用 `epoll` 来监控。在监控的回调中使用传入的 `WindowInputEventReceiver` jobject 指针反射调用其中的方法。反射调用的方法会触发 `ViewRootImpl` 中的对应逻辑。

通过上面的持有关系，Native 层在收到来自于内核的事件后，会通过在对应的 服务端 fd 上发送消息，从而触发 `epoll` 监听。`epoll` 回调就会把这个监听的信息发送到 `ViewRootImpl`.

<img src="android/interview/event/resources/1.png" style="width:100%">


#### Native 如何知道将事件发送给哪个 `InputChannel[0]`


