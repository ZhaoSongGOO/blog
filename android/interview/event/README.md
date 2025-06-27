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

#### 容器拦截流程

事件拦截是 Android 系统提供的一种机制，允许容器类型组件对事件进行私吞，私吞的事件将不会调用子视图的 dispatchEvent 方法。我们以 LinearLayout 中的实现举例来看。

下面展示的是 LinearLayout 的事件拦截相关逻辑，主要做的事情如下：

> ACTION_DOWN: 代表按下事件，是一次触摸事件的开始。
> mFirstTouchTarget: 记录的是一次完整的触摸事件中，响应的子视图。

1. 如果该事件不是 ACTION_DOWN 事件而且之前的事件都没有子视图响应，那 Android 就认为这个事件也没有进一步发送给子视图的必要了，直接强制拦截 `intercepted = true`。

2. 如果该事件是 ACTION_DOWN 或者之前有子视图响应，那就进入拦截判断。
    - 首先取出 disallowIntercept 标志位，这个标志位代表是否允许容器拦截事件。
    - 如果 disallowIntercept 为 true，那就直接 `intercepted = false;` 表示容器不拦截事件，继续后面的派发流程。
    - 如果 disallowIntercept 为 false，就调用 onInterceptTouchEvent 回调，依据回调结果决定是不是拦截。

```java
// File: ViewGroup.java
// Function: dispatchTouchEvent
public boolean dispatchTouchEvent(MotionEvent ev) {
    // 1. 事件包装，处理，事件链状态更新。
    //......
    // 2. 事件拦截判断
    if (actionMasked == MotionEvent.ACTION_DOWN || mFirstTouchTarget != null) {
        final boolean disallowIntercept = (mGroupFlags & FLAG_DISALLOW_INTERCEPT) != 0;
        if (!disallowIntercept) {
            // Allow back to intercept touch
            intercepted = onInterceptTouchEvent(ev);
        } else {
            intercepted = false;
        }
    } else {
        // There are no touch targets and this action is not an initial down
        // so this view group continues to intercept touches.
        intercepted = true;
    }
    //......
    // 3. 事件派发:
    if(!intercepted){
        // 子视图派发
    }else{
        // 派发给自己
        super.dispatchTouchEvent(ev);
    }
    // 
    //......
}
```

<img src="android/interview/event/resources/3.png" style="width:50%">


如果 disallowIntercept 为 false，那是否拦截的决定权就交给了 onInterceptTouchEvent。下面我们看一下 onInterceptTouchEvent 的几个标准实现。

1. ViewGroup.onInterceptTouchEvent

可以看出如果当前时间是鼠标点击滚动条那就拦截，否则不拦截。在我们大多数移动设备上，是很少有鼠标点击的操作的，可以认为 ViewGroup.onInterceptTouchEvent 默认不对事件做拦截。

```java
public boolean onInterceptTouchEvent(MotionEvent ev) {
    if (ev.isFromSource(InputDevice.SOURCE_MOUSE)
            && ev.getAction() == MotionEvent.ACTION_DOWN
            && ev.isButtonPressed(MotionEvent.BUTTON_PRIMARY)
            && isOnScrollbarThumb(ev.getXDispatchLocation(0), ev.getYDispatchLocation(0))) {
        return true;
    }
    return false;
}
```

2. ScrollView.onInterceptTouchEvent

ScrollView 是一个滚动组件，可以看到的是，其发现事件是 Move 的时候，会开始拦截。这也就意味这，对于 ScrollView 的子组件是永远没法感知到滚动事件的。

```java
// File: ScrollView.java
@Override
public boolean onInterceptTouchEvent(MotionEvent ev) {
    /*
        * This method JUST determines whether we want to intercept the motion.
        * If we return true, onMotionEvent will be called and we do the actual
        * scrolling there.
        */

    /*
    * Shortcut the most recurring case: the user is in the dragging
    * state and they is moving their finger.  We want to intercept this
    * motion.
    */
    final int action = ev.getAction();
    if ((action == MotionEvent.ACTION_MOVE) && (mIsBeingDragged)) {
        return true;
    }
    //...
}
```

#### 子视图组织父容器拦截

为了描述这样的场景，我实现了如下的 demo。在 ViewGroup 中重写了默认的 onInterceptTouchEvent， 让其只对 ACTION_DOWN 放行，其余类型都拦截。当然我可以对任意的类型都拦截，但是这样的话，子视图永远没有机会来干预到容器的拦截，而且也不符合 Android UI 系统的设计哲学：一个标准的容器组件，不应该拦截 ACTION_DOWN 事件, 我们需要让子 View 感知到这个事件，这是 Android 设计哲学之一 "子 View 有机会声明自己对事件的兴趣"

```kotlin
class ParentViewGroup
    @JvmOverloads
    constructor(
        context: Context,
        attrs: AttributeSet? = null,
        defStyleAttr: Int = 0,
    ) : LinearLayout(context, attrs, defStyleAttr) {

        override fun onLayout(
            changed: Boolean,
            l: Int,
            t: Int,
            r: Int,
            b: Int,
        ) {
            super.onLayout(changed, l, t, r, b)
        }

        override fun onInterceptTouchEvent(ev: MotionEvent?): Boolean {
            when (ev?.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    return false
                }
                else -> true
            }
            return true
        }
    }
```

子视图我提供了一个自定义的 View，代码如下，主要是重写了 dispatchTouchEvent 方法，这个方法中如果发现事件是 ACTION_DOWN，就对容器 requestDisallowInterceptTouchEvent，即把 disallowIntercept 设置成 true。这样做就可以阻止父容器对后续事件的强制拦截。

```kotlin
class ChildView(ctx: Context, attrs: AttributeSet? = null, defStyleAttr: Int = 0) : View(ctx, attrs, defStyleAttr) {
    constructor(ctx: Context) : this(ctx, null, 0) {}
    constructor(ctx: Context, attr: AttributeSet) : this(ctx, attr, 0) {}

    private val fillPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply { style = Paint.Style.FILL }

    // 画了一个红色背景的圆
    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val centerX = width / 2f
        val centerY = height / 2f
        val maxRadius = (Math.min(width, height) - paddingLeft - paddingRight) / 2f
        fillPaint.color = Color.RED
        canvas.drawCircle(centerX, centerY, maxRadius, fillPaint)
    }

    override fun dispatchTouchEvent(event: MotionEvent?): Boolean {
        when (event?.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                parent?.requestDisallowInterceptTouchEvent(true)
            }
        }
        return super.dispatchTouchEvent(event)
    }
}

```

为什么这样做就可以阻止父组件拦截了呢？我们可以分析一次点击事件发来时整体流程：
1. 容器开始的时候，disallowIntercept 是 false，所以调用 onInterceptTouchEvent，onInterceptTouchEvent 中不会对 ACTION_DOWN 拦截，因此这个事件发送到子视图。
2. 子视图发现是 ACTION_DOWN，就调用 requestDisallowInterceptTouchEvent，容器的 disallowIntercept 变成 true。
3. 后续事件，例如 ACTION_UP 到来的时候，首先看到 disallowIntercept 是 true，就直接不拦截了，此时都不会调用容器的 onInterceptTouchEvent。所以子视图可以继续收到后续的事件。

#### requestDisallowInterceptTouchEvent 影响范围。

之前再想，那加入我有两个子视图，如下所示，设想下面的场景：
1. 先点击 Button，此时不会触发点击事件，因为点击事件需要收到 ACTION_UP 才会触发，而这个事件都被容器拦截了。
2. 然后点击 ChildView 的时候，会触发 requestDisallowInterceptTouchEvent，阻止容器拦截事件。
3. 再次点击 Button 此时会正常触发 Button 的点击事件吗？

上面其实想表达的就是 requestDisallowInterceptTouchEvent 操作设置的状态有效期是多久。如果和容器的生命周期绑定，那上面第三步就会出现 Button 点击生效了。一个 View 的行为会影响另外一个视图听起来就很烧脑，索性 requestDisallowInterceptTouchEvent 的状态生命周期是和事件链绑定的，再每一次 ACTION_DOWN 发起时，都会重置这个状态。

```xml
<com.uiapp.uitest.event.ParentViewGroup xmlns:android="http://schemas.android.com/apk/res/android"
    android:orientation="vertical"
    android:layout_width="match_parent"
    android:layout_height="match_parent"
    android:background="@drawable/green_shape">

    <com.uiapp.uitest.event.ChildView
        android:layout_width="100dp"
        android:layout_height="100dp"
        android:id="@+id/first"/>

    <Button
        android:layout_width="wrap_content"
        android:layout_height="wrap_content"
        android:text="Click2"
        android:id="@+id/second"/>

</com.uiapp.uitest.event.ParentViewGroup>
```

```java
//File: ViewGroup.java

public boolean dispatchTouchEvent(MotionEvent ev) { 
    //...
    if (actionMasked == MotionEvent.ACTION_DOWN) {
        //...
        resetTouchState();
    }
    //...
}

private void resetTouchState() {
    clearTouchTargets();
    resetCancelNextUpFlag(this);
    mGroupFlags &= ~FLAG_DISALLOW_INTERCEPT; // 重置这个状态
    mNestedScrollAxes = SCROLL_AXIS_NONE;
}
```


### 视图遮盖会影响事件响应吗？

#### 上层视图可以响应事件

测试点击层叠区域，只有上层视图响应。很正常，因为上层视图响应后，容器就不会进一步 child.dispatchTouchEvent 了。

#### 上层视图不响应事件

那就由下层视图响应，其实这些都可以有之前的分析推到出来。


### ScrollView 默认无法响应用户自定义的点击事件是为啥？

ScrollView 是一个古老的可滑动组件，当其子视图尺寸大于自身尺寸是，其可以让子视图在其内部滚动展示。我在一次使用中，心血来潮的给 ScrollView 绑定了一个点击事件，但是发现这个事件无法触发，所以下面就来分析一下为什么？

#### 通识

在上面的学习中，我们已经知道点击事件的触发流程经历过如下路径：

```java
dispatchTouchEvent: 用来决定是谁响应，如果响应就继续调用，否则返回
        -> OnTouchListener: 执行 listener，如果返回 true，则返回，不进一步消费。
            -> onTouchEvent : 函数内部对 TouchEvent 进行响应，如果判决为点击事件，就会触发 performClick 执行用户绑定的点击事件监听。
                -> performClick
```

#### 差异

我们可以看到 performClick 的直接触发者是 onTouchEvent 方法，对于绝大多数的视图已经容器都没有对 onTouchEvent 做修改，所以一般我们可以给任意的 View 设置点击事件监听。但是 ScrollView 不一样，他重写了 onTouchEvent 方法，在他自己的 onTouchEvent 方法中没有执行 performClick 方法，因此绑定的点击事件是无效的。

#### 如何让 ScrollView 响应点击事件呢

作为一个对事件系统略有了解的我们，偏要想个办法来触发点击事件。思路也很简单，既然 ScrollView.onTouchEvent 没有调用 performClick, 那我们就要在合适的时机进行触发，需要注意的是，我们在触发过程中，还需要同时保留其原有的滚动特性。

```kotlin
class ScrollViewDemoActivity : Activity() {
    override fun onPostCreate(savedInstanceState: Bundle?) {
        super.onPostCreate(savedInstanceState)
        setContentView(R.layout.activity_scrollview_demo_activity)
        val scrollView = findViewById<ScrollView>(R.id.scrollView)

        // 既然 ScrollView 在 onTouchEvent 中没有触发点击事件，那我们就注册一个  OnTouchListener，
        // 当检测到点击完成时 (ACTION_UP 到来) 就手动触发 performClick。
        // 同时为了不影响自有的滚动逻辑，这个 listener 返回 false 以使得事件继续消费到 onTouchEvent。
        scrollView.setOnTouchListener { v, event ->
            when(event.actionMasked) {
                MotionEvent.ACTION_UP -> {
                    v.performClick()
                }
            }
            false
        }

        scrollView.setOnClickListener {
            clickInfo.text = "点击事件: ScrollView 被点击"
        }
    }
}

```



