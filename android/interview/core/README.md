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


## Activity 是什么？


## WMS 是什么？