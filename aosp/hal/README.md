# HAL (Hardware abostract layer)

> HAL 的作用有两个，第一向上给用户屏蔽了不同硬件设备的差异，第二HAL层是 apache 协议，厂商将自己的硬件相关逻辑放在 HAL 层，可以不开源。如果放在内核中，就需要和内核一块公开源代码了。

## 架构

HAL 在 android 上的发展分成三个阶段：

1.  HAL 阶段 (<8)

在远古阶段，HAL 以 so 包的形式存在，java framwork 通过 jni 来访问。并向上通过 binder 服务的形式服务于应用层。

<img src="aosp/hal/resources/hal_1.png" style="width:50%"/>

2. HIDL + HAL 阶段 (8-10)

这个阶段 HAL 以 binder 服务的形式存在。java framwork 通过 binder 服务调用的方式来访问。并向上通过 binder 服务的形式服务于应用层。

3. AIDL + HAL 阶段 (>11)

这个阶段，应用层不仅可以通过调用通过 binder 服务的方式来访问 HAL，还可以通过 AIDL 好、直接访问。

<img src="aosp/hal/resources/hal_2.png" style="width:50%"/>


## 远古阶段 HAL 调用流程


<img src="aosp/hal/resources/hal_3.png" style="width:100%"/>

1. App 调用 `getSystemService` 函数。
2. 这个函数在基类中实现成调用 `ContextImp` 对象。
3. `ContextImp` 对象调用 SystemServiceRegister 对象，这个对象会注册很多 java 版本的 SystemXXXService 对象。
4. Java 版本的 SystemXXXService 对象 中持有对应的硬件服务代理，这里就是 `IVibratoeService`, 所有的具体操作都是通过这个代理实现的。
5. `IVibratoeService` 与 SystemService 中的对应 Binder 服务通信。
6. Binder 服务通过 jni 调用 hal.so 中的具体能力。

