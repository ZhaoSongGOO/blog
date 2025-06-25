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

<img src="android/interview/event/resources/1.png" style="width:80%">


#### Native 如何知道将事件发送给哪个 `InputChannel[0]`

同一时刻，我们设备上会有多个窗口，这里面每个窗口都对应着一个 ViewRootImpl，那我们在设备上进行点击的时候，系统又是如何确认点击事件应该发给哪个窗口呢？

- 首先判断事件是不是发生在当前焦点窗口，如果是，那目标窗口就是焦点窗口。
- 按照窗口的 z-index 顺序，从上到下去判断。

系统在 Native层 存储着所有的 Window 对应的 C++ 对象，这些对象与 InputChannel[0] 一一绑定，如果我们确定是哪个 Window 对象被点击，那就可以拿到对一个的 fd，通过这个 fd，就可以将事件正确的发送到应用层的 ViewRootImpl。


## 事件处理

在上面我们讲了事件发生的大概流程，以及应用层 ViewRootImpl 作为应用层事件接收对象的事实，本节从 ViewRootImpl 收到事件后为起点，介绍其在应用层消费的过程。


<img src="android/interview/event/resources/2.png" style="width:120%">


### 接收

在上面我们已经提到了系统的事件会通过 JNI 触发对应的 ViewRootImpl 中的 WindowInputEventListener 回调方法 onInputEvent。 onInputEvent 通过一些事件的处理后将事件发送到 ViewRootImpl 中定义的一个事件处理职责链，这个责任链会依据事件的类型进行消费，不消费就继续向下传递，对于我们屏幕的触摸事件，会发送到 ViewPostImeInputStage 这个阶段，这个阶段调用其 processPointerEvent 方法来进行事件分发。

```java
native
|
V
ViewRootImpl.WindowInputEventListener.onInputEvent
|
V
ViewRootImpl.enqueueInputEvent
|
V
ViewRootImpl.deliverInputEvent
|
V
ViewRootImpl.ViewPostImeInputStage.postPointerEvent
```


### 上传

因为 ViewRootImpl 持有着视图根 DecorView，所以在 postPointerEvent 阶段直接调用了 DecorView 的 dispatchPointerEvent 方法进行事件上传。

```java
// ViewRootImpl.java
private int processPointerEvent(QueuedInputEvent q) {
    //...
    boolean handled = mView.dispatchPointerEvent(event);
    //...
```

之所以叫上传是因为 DecorView 收到这个事件后，并没有急着在整个 UI 树上进行事件分发，而是通过 Window 上传到 Activity。最后再由 Activity 传回 DecorView，这个步骤看似多余，其实是想让 Activity 感知到事件并进行事件兜底，目的是在整个视图树上没有找到对应的 View 去消费事件的时候，由 Activity 进行处理。

dispatchTouchEvent 这个方法接收一个事件参数，返回一个布尔值，如果返回 true，代表事件已经被消费，否则代表不消费传入的事件。

```java
//Activity.java
public boolean dispatchTouchEvent(MotionEvent ev) {
    if (ev.getAction() == MotionEvent.ACTION_DOWN) {
        onUserInteraction();
    }
    if (getWindow().superDispatchTouchEvent(ev)) { // Activity 再将事件返回给 DecorView
        return true;
    }
    return onTouchEvent(ev); // 如果没有任何 View 消费这个事件，那调用 Activity 自身的事件处理监听。
}

```
### 下达

Activity 把事件再次交给 DecorView 后，DecorView 会调用自身的 dispatchTouchEvent 方法，这个方法由其祖父类 ViewGroup 实现，在这个方法中按序进行下面三个操作。

1. 判断当前 ViewGroup 是不是拦截该事件，如果拦截的话，转掉父类(View)的 dispatchTouchEvent。
2. 如果不拦截，那在自己的孩子中 dispatchTouchEvent，期望孩子可以响应时间，如果孩子响应了事件，那就结束。
3. 如果孩子不响应事件，那就自己调用父类的 dispatchTouchEvent，看下自己是不是需要响应。

```java
//ViewGroup.java

boolean dispatchTouchEvent(MotionEvent ev){
    boolean intercepted = onInterceptTouchEvent(ev);
    if(intercepted){
        return super.dispatchTouchEvent(ev)
    }  
    boolean result = false;
    result = child.dispatchTouchEvent(ev);
    if(!result){
        result = super.dispatchTouchEvent(ev);
    }
    return result;
}
```

上面可以看到，其实不管是哪个路径，最后都调用到了 View.dispatchTouchEvent(ev) 进行处理。移除了一些无障碍以及调试相关的逻辑，我们下面看一下这个方法的实现。

重点在代码中已经做了注释，这里说明一个关键点，一个 View 在消费触摸事件的时候，首先会交给 OnTouchListener 去消费，如果 OnTouchListener 返回 true，那就不会触发 onTouchEvent。

同时你需要知道我们一般定义的点击事件回调是在 onTouchEvent 中才会被触发的，这也就意味着，如果我们的 OnTouchListener 错误的消费了所有的事件，那我们的点击事件将永远不会触发。

```java
// View.java

    /**
     * Pass the touch screen motion event down to the target view, or this
     * view if it is the target.
     *
     * @param event The motion event to be dispatched.
     * @return True if the event was handled by the view, false otherwise.
     */
    public boolean dispatchTouchEvent(MotionEvent event) {
        boolean result = false;

        final int actionMasked = event.getActionMasked();
        // 如果这是一次 按下的 Touch 事件，这代表着事件的开始，因此我们清空之前的事件
        if (actionMasked == MotionEvent.ACTION_DOWN) {
            // Defensive cleanup for new gesture
            stopNestedScroll();
        }
        // 进行一些安全校验
        if (onFilterTouchEventForSecurity(event)) {
            //noinspection SimplifiableIfStatement
            // 如果用户注册了 TouchEvent 的事件监听，那就调用这个监听，并且这个监听如果消费了事件，那就将 result 设置成 true。
            ListenerInfo li = mListenerInfo;
            if (li != null && li.mOnTouchListener != null
                    && (mViewFlags & ENABLED_MASK) == ENABLED
                    && li.mOnTouchListener.onTouch(this, event)) {
                result = true;
            }

            // 如果事件还没有被消费，那就调用自己的 TouchEvent 方法。如果 TouchEvent 消费了事件，那就设置消费状态为 true。
            if (!result && onTouchEvent(event)) {
                result = true;
            }
        }
        // 如果该事件是抬起、取消，或者虽然是按下，但是该视图并不消费，那就取消事件记录。
        if (actionMasked == MotionEvent.ACTION_UP ||
                actionMasked == MotionEvent.ACTION_CANCEL ||
                (actionMasked == MotionEvent.ACTION_DOWN && !result)) {
            stopNestedScroll();
        }

        return result;
    }
```

### (TODO:更详尽的分析) onTouchEvent 分析

刚才提到，我们定义的点击事件都是在 onTouchEvent 中触发的，所以下面对其进行分析。

#### onClickListerner 触发

现阶段呢，我们就对其中在何时触发我们用户的 onClickListerner 进行分析。

在事件为 ACTION_UP 的时候，如果我们手势识别为 Tap，即点击事件的时候，就会触发 PerformClick。这里有个细节就是为了优化点击反馈 UI 体验，尝试将激活点击回调的操作异步执行 post(mPerformClick)，在异步失败的时候进行同步执行 performClickInternal()。这里的异步不是指在其他线程执行回调，而是将点击回调发送到 UI 线程队列中稍后执行。

```java
 switch (action) {
    case MotionEvent.ACTION_UP:
          if (!mHasPerformedLongPress && !mIgnoreNextUpEvent) {
                            // This is a tap, so remove the longpress check
                            removeLongPressCallback();

                            // Only perform take click actions if we were in the pressed state
                            if (!focusTaken) {
                                // Use a Runnable and post this rather than calling
                                // performClick directly. This lets other visual state
                                // of the view update before click actions start.
                                if (mPerformClick == null) {
                                    mPerformClick = new PerformClick();
                                }
                                if (!post(mPerformClick)) {
                                    performClickInternal();
                                }
                            }
                        }
 }

```

performClickInternal 还是 post(mPerformClick) 最终都会执行 performClick 方法。这个方法如下：

内容非常简单，就是简单的触发用户写的 onClickListener 的 onClick 方法，传入的参数就是自身。

```java
// View.java
public boolean performClick() {
    // We still need to call this method to handle the cases where performClick() was called
    // externally, instead of through performClickInternal()
    notifyAutofillManagerOnClick();

    final boolean result;
    final ListenerInfo li = mListenerInfo;
    if (li != null && li.mOnClickListener != null) {
        playSoundEffect(SoundEffectConstants.CLICK);
        li.mOnClickListener.onClick(this);
        result = true;
    } else {
        result = false;
    }

    sendAccessibilityEvent(AccessibilityEvent.TYPE_VIEW_CLICKED);

    notifyEnterOrExitForAutoFillIfNeeded(true);

    return result;
}
```


## 几个问题

### 子视图如何阻止父亲视图拦截事件？

事件拦截是 Android 系统提供的一种机制，允许容器类型组件对事件进行私吞，私吞的事件将不会调用子视图的 dispatchEvent 方法。我们以 LinearLayout 中的实现举例来看。

```java

```


### 视图遮盖会影响事件响应吗？


### ScrollView 默认无法响应用户自定义的点击事件是为啥？

