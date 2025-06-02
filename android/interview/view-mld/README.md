# View 的 Measure 、Layout 、Draw 流程分析

> 本文总阅读量 <span id="busuanzi_value_page_pv"><i class="fa fa-spinner fa-spin"></i></span>次
---

## View 类继承体系

<img src="android/interview/view-mld/resources/mld_1.png" style="width:50%">



`View` 是一个基类，是用户界面的基本组件，一个 `View` 占据屏幕上的一个矩形区域。并且负责对应的绘制以及视图处理，它派生出来两个子类：
- 具体的视图组件，例如 `TextView`  、`ImageView` 等。
- 可以包含子视图的容器组件，例如 `LinearLayout`。

## 渲染流程

<img src="android/interview/view-mld/resources/mld_2.png" style="width:70%">

先从整体来看，一次 `View` 树到手机上实际的 UI 视图在应用层经历大致的一个流程是：

1. `trigger`: UI 渲染流程的触发源，收到这个信号后，整个系统开始进行 UI 渲染。
2. `measure`: 测量过程，用来确定每一个 `View` 的宽高尺寸。
3. `layout`: 布局过程，用来确定每一个 `View` 在屏幕中的位置。
4. `draw`: 绘制过程，将具体的内容在已经确定好的范围内进行绘制，绘制的信息后续会被系统消费渲染。

## 渲染触发源 trigger

### VSync

`VSync` (Vertical Synchronization) 垂直同步是显卡与显示器之间的同步机制。简单的理解，以 `VSync` 为节拍，显卡和显示器保持同步的数据更新节奏，从而避免画面撕裂等问题。

在 Android 中，对于应用层 UI 的处理，也是以 `VSync` 信号为节拍来进行的。

### 应用层触发

<img src="android/interview/view-mld/resources/mld_3.png" style="width:100%">

在应用层，用来承接 `VSync` 信号的对象叫 `Choreographer`。其收到这个信号后，触发自己的 `doFrame` 函数，这个函数会对注册的一些 `callback` 进行回调。其中就有来自于 `ViewRootImpl` 注册的 `doTraversal` 方法。 `doTraversal` 中会按序执行 `measure`、`layout`、`draw`。

### 回调何时被注册？

> 同步屏障：设置同步屏障后，将会对屏障后的所有同步任务暂停，只运行异步任务。而我们 `mTraversalRunnable` 这个任务是异步任务。

上面提到了 `ViewRootImpl` 注册的 `doTraversal`，那这个回调是什么时候被注册的？

- 用户对 UI 属性进行变更，例如更改了某个 UI 的颜色。
- 显式调用 `requestLayout` 等方法。

```java
// ViewRootImpl.java
void requestLayout(){
    //...
    void scheduleTraversals() {
        if (!mTraversalScheduled) { // 避免重入
            mTraversalScheduled = true;
            mTraversalBarrier = mHandler.getLooper().getQueue().postSyncBarrier(); // 设置同步屏障
            mChoreographer.postCallback(
                    Choreographer.CALLBACK_TRAVERSAL, mTraversalRunnable, null); // 注册回调
            //...
        }
    }
}
```

因为上面有避免重入机制，所以我们在一帧之内的重复 `requestLayout` 只会注册一次回调。同时设置同步屏障，可以确保 UI 遍历的操作不会被其他非异步任务阻塞。

### 回调被触发

在收到 `VSync` 信号后，回调被触发，触发后，关掉标志位，同时关闭同步屏障。但是你要知道，此时正在运行的任务就是 UI 遍历任务。所以移除了也不会被其他任务占用。

```java
// ViewRootImpl.java
void doTraversal() {
    if (mTraversalScheduled) { 
        mTraversalScheduled = false; 
        mHandler.getLooper().getQueue().removeSyncBarrier(mTraversalBarrier); // 移除同步屏障
        //...
        // 执行 UI 遍历操作
        performTraversals(); // 这里面如果 requestLayout, 那只能等到下一帧才会被触发。
        //...
    }
}
```

### 触发后呢？

触发后的回调会被队列移除，也就是说，如果我们在一帧之内没有做任何 UI 相关操作，那下一次 `VSync` 来的时候，就不会触发 UI 遍历操作。

### 如果我们在一帧内发起多次 requestLayout 会发生什么？

设想如下的场景，我连续快速的修改了一个 UI 的宽度，每一次修改会触发一次布局请求，但是从上面的情况可以得知，只有第一次的 `requestLayout` 对应的 `scheduleTraversals` 才会被注册 `callback`。也就是说在 `VSync` 到来后，只会触发一次遍历操作。那第二次的宽度更改操作会生效吗？

```java
ui.width = 100dp;
ui.width = 200dp;
```

会的！虽然只有第一次的 尺寸变更会触发回调注册，但是两次的宽度数据都会被设置到 UI 属性上，而且第二次的 `200dp` 会覆盖第一次的 `100dp`，即丢弃了第一次的变更数据。


## 布局研究范围

我们在开发的过程中，会在布局 XML 文件中或者在代码中手动进行 UI 增删以及属性设置。这些 UI 属于我们用户自定义的部分，但是在一个 `Activity` 中展示的 UI 除了用户自定义的部分，还包括一部分系统默认设置的组件。本小节我们就看一下系统默认增加了哪些内容，从而进一步明确在一次绘制过程中我们到底需要针对于哪些 UI 去做测算。

### 树根 DecorView

`DecorView` 是整个 `Activity` 视图树的根容器，从上面的类继承层次也可以看到，它是一个 `FrameLayout` 的子类。下面展示了相关的几个类的关系。

<img src="android/interview/view-mld/resources/mld_5.png" style="width:100%">

1. 创建

在每一个 `Activity` 创建的时候，会创建一个对应的 `PhoneWindow` 对象，这个 对象会创建一个 `DecorView` 对象。

```java
// Activity.java construct
mWindow = new PhoneWindow(this, window, activityConfigCallback);

// PhoneWindow.java construct
mDecor = (DecorView) preservedWindow.getDecorView();
```

2. 添加

我们在每个 `Activity` 的 `onCreate` 方法中使用 `setContentView` 加载我们的布局文件。在这个过程中，`Activity` 直接转到 `Window` 对象的 `setContentView` 方法。将 XML 对应的布局 id 作为孩子绑定在 DecorView 视图上。

```java
// PhonwWindow.java
public void setContentView(int layoutResID) {
        // 如果没有 DecorView 或者没有生成 DecorView 的 布局 id，就 install 一下。
        if (mContentParent == null) {
            installDecor();
        } else if (!hasFeature(FEATURE_CONTENT_TRANSITIONS)) {
            mContentParent.removeAllViews();
        }

        if (hasFeature(FEATURE_CONTENT_TRANSITIONS)) {
            final Scene newScene = Scene.getSceneForLayout(mContentParent, layoutResID,
                    getContext());
            transitionTo(newScene);
        } else {
            // 把 xml 的布局作为孩子添加到 decorView 上
            mLayoutInflater.inflate(layoutResID, mContentParent);
        }
}
```

3. 关联

在上面我们分析触发的时候，提到了 `ViewRootImpl` 对象，这个对象承载了监听 VSync 回调，并对视图树进行遍历操作的责任。所以我们需要将以 `DecorView` 为根的这棵树与 `ViewRootImpl` 进行关联。

`Activity` 在变的可见的时候，会通过 `PhoneWindow` 对象调用到 `WindowManagerImpl`, 并将刚才创建的 `DecorView` 传入。 进而在一个全局单例 `WindowManagerGlobal` 中创建 `ViewRootImpl`, 同时将传入的 `DecorView` 与 `ViewRootImpl` 进行绑定。

```java
// Activity.java
void makeVisible() {
    if (!mWindowAdded) {
        ViewManager wm = getWindowManager();
        wm.addView(mDecor, getWindow().getAttributes());
        mWindowAdded = true;
    }
    mDecor.setVisibility(View.VISIBLE);
}

```

```java

// WindowManagerImpl.java
public void addView(@NonNull View view, @NonNull ViewGroup.LayoutParams params) {
    applyTokens(params);
    mGlobal.addView(view, params, mContext.getDisplayNoVerify(), mParentWindow,
            mContext.getUserId());
}

```

```java

// WindowManagerGlobal.java
// addView function
// 创建 ViewRootImpl
if (windowlessSession == null) {
    root = new ViewRootImpl(view.getContext(), display);
} else {
    root = new ViewRootImpl(view.getContext(), display,
            windowlessSession, new WindowlessWindowLayout());
}
view.setLayoutParams(wparams);
// 统一记录
mViews.add(view);
mRoots.add(root);
mParams.add(wparams);
// do this last because it fires off messages to start doing things
try {
// 绑定
    root.setView(view, wparams, panelParentView, userId);
} catch (RuntimeException e) {
    final int viewIndex = (index >= 0) ? index : (mViews.size() - 1);
    // BadTokenException or InvalidDisplayException, clean up.
    if (viewIndex >= 0) {
        removeViewLocked(viewIndex, true);
    }
    throw e;
}
```

### 手机屏幕的组成

<img src="android/interview/view-mld/resources/mld_4.png" style="width:20%"><img src="android/interview/view-mld/resources/mld_6.png" style="width:60%">

上文提到，我们一个 `Activity` 的 UI 树根节点是 `DecorView`，其本质是一个 `FrameLayout`，其内部直接持有一个 `LinearLayout` 布局，这个布局中，从上到下添加了 `StatusBar` 、`TiTleBar`、`Content`(FrameLayout)、`NavigationBar` 等组件。

- `StatusBar`: 用来显示电量 、时间、网络状态等内容，由系统管理，不参与 UI 排版。
- `TitleBar`: 有时候也叫 `ActionBar`，用来展示 `Activity` 的标题， 本身是一个 `FrameLayout`，我们一般可以手动设置展示或者隐藏。会参与 UI 排版。
- `Content`: 用来盛放用户页面数据的容器，本身也是一个 `FrameLayout`，其子视图才是XML文件中写的内容，这部分参与 UI 排版。
- `NavigationBar`: 导航栏，系统控制，不参与排版。以前用来盛放返回键 、Home 键等UI。现在基本已经被手势操作取代了。

### UI 渲染简化

为了更方便的分析 UI 渲染过程，我们做出如下假设以简化 UI 树结构。

1. 我们的 UI 没有 `TitleBar`.
2. 我们的 XML 文件相对比较简单。

```xml
<LinearLayout xmlns:android="http://schemas.android.com/apk/res/android"
    android:layout_width="match_parent"
    android:layout_height="match_parent">
    <TextView
        android:layout_height="wrap_content"
        android:layout_width="wrap_content"
        android:background="#ff0000"
        android:text="hello"/>
    <Button
        android:layout_height="wrap_content"
        android:layout_width="wrap_content"
        android:background="#00ff00"
        android:text="Submit"/>
</LinearLayout>
```

在此假设下，我们的 UI 树变成如下的样子：

<img src="android/interview/view-mld/resources/mld_7.png" style="width:25%">


## Measure 启动！

### 布局整体流程图

<img src="android/interview/view-mld/resources/mld_8.png" style="width:100%">

Android 的所有 UI 组成了一个树结构，并在每个 VSync 到来的时候，如果有需要就以广度优先遍历的方式对整个 UI 树进行测算。在每一个测算的过程(函数)中，每一种不同的容器组件或者具体的视图组件都会做不同的测算处理，这里面涉及了非常多的细节和边界情况，为了避免陷入困惑，我们暂时不去考虑这些特殊的逻辑，从关键流程和关键输入输出来描述整个过程。

### 测算关键函数

在讲解整个流程前，我们先看一下这个 measure 过程中关键的两个函数。


#### `measure`

用来进行 measure 操作的函数，这是一个 final 的方法，由 View 基类实现，子类无法修改。
输入参数是父容器传递的约束条件，这只是一个建议值，当前视图可以做受限的调整。

```java
// View.java
final void measure(int widthMeasureSpec, int heightMeasureSpec) {
    //...
    onMeasure(widthMeasureSpec, heightMeasureSpec);
    //...
}
```

#### `onMeasure`

刚才提到了当前视图可以对父容器传递进来的约束条件进行受限调整，那在哪里调整呢？既然 `measure` 方法是个 final 的方法，那子类是没办法在这个方法中进行自定义以调整的。好在 `View` 提供了一个 `onMeasure` 的子类可自定义方法，我们可以在这个方法中进行 UI 尺寸的的调整与设置。同时 `View` 的 `measure` 方法确保 `onMeasure` 方法一定会被调用到。

`onMeasure` 中一般按序做两件事情：
1. 在一定的限制条件下按需计算自己的尺寸。

子 View 对于尺寸的的调整不是我们想调整多少就调整多少的，如果没有按照限制去做调整，会降级到直接使用父容器的约束尺寸。

<img src="android/interview/view-mld/resources/mld_9.png" style="width:40%">

2. 调用 `setMeasuredDimension` 设置自己计算的结果，如果不设置，会直接抛出异常。

```java
protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
    //....
    int finalWidth = calculateFinalWidth(...);
    int finalHeight = calculateFinalHeight(...);
    //....
    // 必须调用！
    setMeasuredDimension(finalWidth, finalHeight);
}
```

当然子类完全可以使用 `onMeasure` 的默认定义，默认定义如下，忽略一些细节，默认的 `onMeasure` 中会判断父容器传递进来的约束条件：
- 如果约束条件是 `UNSPECIFIED`, 那就是用建议的尺寸。(至于什么是建议的尺寸，就先不管了)
- 如果约束条件是 `AT_MOST` 和 `EXACTLY`, 那就直接使用父容器传进来尺寸。

```java
// View.java
protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
    setMeasuredDimension(getDefaultSize(getSuggestedMinimumWidth(), widthMeasureSpec),
            getDefaultSize(getSuggestedMinimumHeight(), heightMeasureSpec));
}

public static int getDefaultSize(int size, int measureSpec) {
    int result = size;
    int specMode = MeasureSpec.getMode(measureSpec);
    int specSize = MeasureSpec.getSize(measureSpec);

    switch (specMode) {
    case MeasureSpec.UNSPECIFIED:
        result = size;
        break;
    case MeasureSpec.AT_MOST:
    case MeasureSpec.EXACTLY:
        result = specSize;
        break;
    }
    return result;
}

```

### 测算过程解析

1. `VSync` 信号到达，`Choreographer` 调用 `ViewRootImpl` 注册的 UI 遍历回调。
2. `ViewRootImpl` 收到后，调用 `doTraversals` 方法，在这个方法中如果判断确实需要重新计算，那就再一次调用 `performTraversals` 方法。
3. `performTraversals` 获取到 `rootMeasureSpec`，然后用这个 root 的 measure 参数调用 `performMeasure` 方法
> `rootMeasureSpec` 包括 `childWidthMeasureSpec` 和 `childHeightMeasureSpec`:
> `childWidthMeasureSpec`: value = window_width, mode = EXACTLY
> `childHeightMeasureSpec`: value = window_height, mode = EXACTLY
4. `performMeasure` 做了简单的操作后，以 `rootMeasureSpec` 为参数直接调用 `decorView.measure` 方法。刚才提供了 `measure` 是 final 的，由 `View` 来实现。
5. `View` 在 `measure` 执行中，调用 `onMeasure` 方法，这个会调用到 `DecorView` 的 `onMeasure` 方法。
6. `DecorView` 本身是一个 `FrameLayout` 的子类，它在自己的 `onMeasure` 中做了一些简单的操作后，就调用了父类(`FrameLayout`)的 `onMeasure` 方法。
7. `FrameLayout` 的 `onMeasure` 方法非常的复杂，充斥着各种情况的判断，但是整体上是按序遍历自己的孩子，生成孩子的约束，并依次调用 `childView.measure` 方法。之前的研究范围一节中，我们说了 `DecorView`` 的直接子孩子是一个 LinearLayout`。所以上一步中 `childView` 本身是一个 `LinearLayout` 对象。
8. 同样的 `LinearLayout` 的 `measure` 从 `View` 那里转了一圈又回到了自己的 `onMeasure` 方法中。线性布局分为水平和垂直两个方向，所以有下面两个不同的处理逻辑，这里我们就以垂直布局为例继续分析 `measureVertical`。

```java
protected void onMeasure(int widthMeasureSpec, int heightMeasureSpec) {
    if (mOrientation == VERTICAL) {
        measureVertical(widthMeasureSpec, heightMeasureSpec);
    } else {
        measureHorizontal(widthMeasureSpec, heightMeasureSpec);
    }
}
```
9. 在这个 `measureVertical` 中，和 `FrameLayout` 一样，也是进行了按序遍历自己的孩子，生成孩子的约束，并依次调用 `childView.measure` 方法三个步骤。
10. 接下来就调用到我们承载用户 XML 视图的容器 Content 了，整理流程如上，就不一一赘述了。

### 孩子约束生成策略

在容器组件的 `onMeasure` 中，一般会有三个步骤：

1. 进行自己的布局处理。
2. 生成孩子约束条件。
3. 使用孩子的约束条件作为参数，调用 `childView.measure` 方法。

这里1和3没什么多说的，暂时也看不明白。但是生成孩子约束这块我们可以稍微的了解一下，这有助于帮助我们对于写 XML 时的属性做更深层次的理解。

"Does the hard part of measureChildren" 这句话出现在 `getChildMeasureSpec` 这个函数的注释中，但是这个函数在逻辑上来看非常的清晰，不是多么困难。

#### 接收参数

```java
public static int getChildMeasureSpec(int spec, int padding, int childDimension) {
    // 函数实现...
}
```

1. `spec` 当前容器的测量约束。即子视图的宽高约束可能会受到父容器宽高约束的影响。再次强调，当前容器的约束，不是当前容器对孩子的约束。
2. `padding` 当前容器的内边距。
3. `childDimension` 子视图的尺寸需求。这里需要补充一下 `measureSpec` 与 `dimension` 的区别。

##### MeasureSpec 与 dimension

`MeasureSpec` 是一个 Android 布局过程中父组件对于当前 UI 进行宽高进行约束的综合属性。他是一个 32 位的整数，其中 2 位拿来存储宽高模式 mode，30 位拿来记录宽高的具体数值 size。

下面列举了约束的三个模式：

- UNSPECIFIED: 父组件对你没约束，你爱多大多大。
- EXACTLY: 父组件要求你是指定的尺寸。
- AT_MOST: 父组件给你个最大的尺寸，你可以在这个范围内随意调整。

```java
// View.java:public static class MeasureSpec
/**
 * Measure specification mode: The parent has not imposed any constraint
 * on the child. It can be whatever size it wants.
 */
public static final int UNSPECIFIED = 0 << MODE_SHIFT;

/**
 * Measure specification mode: The parent has determined an exact size
 * for the child. The child is going to be given those bounds regardless
 * of how big it wants to be.
 */
public static final int EXACTLY     = 1 << MODE_SHIFT;

/**
 * Measure specification mode: The child can be as large as it wants up
 * to the specified size.
 */
public static final int AT_MOST     = 2 << MODE_SHIFT;
```

`dimension` 的原始类型是 `LayoutParams` 的一个字段 `width` 和  `height`，其是由 XML 中我们设置的 `layout_widhth` 和 `layout_height` 属性转换而来，其有三种原始类型。

- MATCH_PARENT: 标明当前组件的尺寸想和父组件尽可能一样大。
- WRAP_CONTENT: 标明当前组件想调整自己的尺寸去容纳自己内部元素。
- 大于等于0的具体值: 我们一般会使用 `layout_width:100dp` 这样的方式来直接设置具体的尺寸。

```java
/**
 * Special value for the height or width requested by a View.
 * MATCH_PARENT means that the view wants to be as big as its parent,
 * minus the parent's padding, if any. Introduced in API Level 8.
 */
public static final int MATCH_PARENT = -1;

/**
 * Special value for the height or width requested by a View.
 * WRAP_CONTENT means that the view wants to be just large enough to fit
 * its own internal content, taking its own padding into account.
 */
public static final int WRAP_CONTENT = -2;
```

#### 测算流程

在这个函数中，会依据传入的 `spec` 值来分场景进行子视图测算。

##### spec 为 EXACTLY

父容器约束条件为 EXACTLY， 即父容器拥有一个具体的数值。

- 孩子在 XML 中设置了具体的尺寸，那孩子的约束条件就是 EXACTLY， 尺寸为 XML 中设定的数值。
- 孩子在 XML 设置的是 match_parent, 因为父容器尺寸是固定的，所以直接把孩子的约束条件设置成 EXACTLY，尺寸等于父容器尺寸。
- 还在在 XML 设置的是 wrap_content, 想依据自己的内容来调整，但是因为父容器是固定尺寸，所以孩子的约束条件设置成 AT_MOST，且最大尺寸上限为父容器尺寸。
> 这就说明子视图只能在父容器尺寸范围内进行尺寸调整以实现 wrap_content。

```java
case MeasureSpec.EXACTLY:
    if (childDimension >= 0) {
        resultSize = childDimension;
        resultMode = MeasureSpec.EXACTLY;
    } else if (childDimension == LayoutParams.MATCH_PARENT) {
        // Child wants to be our size. So be it.
        resultSize = size;
        resultMode = MeasureSpec.EXACTLY;
    } else if (childDimension == LayoutParams.WRAP_CONTENT) {
        // Child wants to determine its own size. It can't be
        // bigger than us.
        resultSize = size;
        resultMode = MeasureSpec.AT_MOST;
    }
    break;
```

##### spec 为 AT_MOST

父容器的约束模式为 AT_MOST，意味着父容器可以在设定的上线内，动态的调整自己的尺寸。

- 孩子在 XML 中设置了具体的尺寸，那孩子的约束条件就是 EXACTLY， 尺寸为 XML 中设定的数值。
- 孩子在 XML 设置的是 match_parent, 因为父容器尺寸是有上限的，所以孩子的约束条件也被设置成 AT_MOST，而且上限为父容器的约束上限。
- 还在在 XML 设置的是 wrap_content, 想依据自己的内容来调整，但是因为父容器也是有上限的，所以孩子的约束条件设置成 AT_MOST，而且上限为父容器的约束上限。

```java
case MeasureSpec.AT_MOST:
    if (childDimension >= 0) {
        resultSize = childDimension;
        resultMode = MeasureSpec.EXACTLY;
    } else if (childDimension == LayoutParams.MATCH_PARENT) {
        resultSize = size;
        resultMode = MeasureSpec.AT_MOST; // 注意不是EXACTLY!
    } else if (childDimension == LayoutParams.WRAP_CONTENT) {
        resultSize = size;
        resultMode = MeasureSpec.AT_MOST;
    }
    break;
```

##### spec 为 UNSPECIFIED

父容器的尺寸没有被限制，想多大就多大。

- 孩子在 XML 中设置了具体的尺寸，那孩子的约束条件就是 EXACTLY， 尺寸为 XML 中设定的数值。
- 孩子在 XML 设置的是 match_parent 或者 wrap_content

```java
case MeasureSpec.UNSPECIFIED:
    if (childDimension >= 0) {
        resultSize = childDimension;
        resultMode = MeasureSpec.EXACTLY;
    } else if (childDimension == LayoutParams.MATCH_PARENT) {
        resultSize = size; // 通常为0
        resultMode = MeasureSpec.UNSPECIFIED;
    } else if (childDimension == LayoutParams.WRAP_CONTENT) {
        resultSize = size;
        resultMode = MeasureSpec.UNSPECIFIED;
    }
    break;
```

## Layout 启动！

`layout` 是整个布局过程的第二阶段，在这个阶段，每一个父容器会调用它的孩子的 `layout` 方法以去定位它们。这阶段会使用一些 `measure` 阶段获取到的一些结果作为辅助。

### layout 关键方法

和 measure 一样，我们先介绍几个和 layout 相关的关键 api。

1. layout

`layout` 方法和 `measure` 不同，不是一个 final 的方法，可以被子类重写，但是一般而言，并不希望子类重写这个方法，如果有需要，还是尽可能的重写 `onLayout` 来实现。

```java
// View.java
public void layout(int l, int t, int r, int b) {
    //...
    boolean changed = isLayoutModeOptical(mParent) ?
                setOpticalFrame(l, t, r, b) : setFrame(l, t, r, b);
    onLayout(changed, l, t, r, b);
    //...
}
```

`layout` 方法接收四个参数，如下图所示，分别代表子视图在父容器坐标系中的上右下左四个距离。

<img src="android/interview/view-mld/resources/mld_10.png" style="width:20%">

随后 `layout` 会使用 setXXXFrame 函数来设置自己的位置，随后调用 onLayout。在调用 onLayout 的时候，会额外传入一个 changed 的参数，这个参数来自于 setXXXFrame 的返回，代表当前视图的位置有没有变更，可以更具需要，选择是否需要执行 onLayout 的实际定位逻辑。

2. onLayout

`onLayout` 和 `onMeasure` 一样，是 Android 测绘系统提供给我们的灵活性，可以看到，View 默认只是提供了空实现。我们可以在自定义 View 或者 自定义的容器内部重写 onLayout 方法来实现自己的定位逻辑。

```java
// View.java
/**
 * Called from layout when this view should
 * assign a size and position to each of its children.
 *
 * Derived classes with children should override
 * this method and call layout on each of
 * their children.
 * @param changed This is a new size or position for this view
 * @param left Left position, relative to parent
 * @param top Top position, relative to parent
 * @param right Right position, relative to parent
 * @param bottom Bottom position, relative to parent
 */
protected void onLayout(boolean changed, int left, int top, int right, int bottom) {}
```

### layout 流程分析

<img src="android/interview/view-mld/resources/mld_11.png" style="width:100%">

1. 和 `performMeasure` 一样，`performLayout` 在其之后被触发。
2. 调用 `DecorView` 的 `layout` 方法，传入的参数为 `(0, 0, mDecorView.getMeasuredWidth, mDecorView.getMeasuredHeight)`
3. `DecorView` 的 `layout` 一路向上调用到 `View`，再由 `View` 触发 `onLayout` 调用，这个方法被 DecorView 重写。
4. `DecorView` 调用了父类，也就是 `FrameLayout` 的 `onLayout` 方法，在 `FrameLayout` 中会对自己的孩子依次计算位置，调用 `childView.layout`。



## Draw 启动！

<img src="android/interview/view-mld/resources/mld_12.png" style="width:100%">

### 整体流程

1. 和前面一致，在 `VSync` 触发后，`ViewRootImpl` 的遍历回调中会在 `measure` 和 `layout` 完成后，进行 `performDraw` 过程。
2. `performDraw` 上来会判断是不是支持了硬件绘制，如果支持就走硬件绘制，否则就走软件绘制。
3. 这里只看软件绘制，软件绘制会和上面一样，直接调用 `mDecorView` 的 `draw` 进行绘制。调用 draw 方法传入了一个 canvas 对象。
4. draw 方法基本进行下面四个主要步骤：
    1. drawBackground: 背景色，背景图等。
    2. onDraw：绘制自身。
    3. dispatchDraw：绘制自己的孩子。调用自己孩子的 draw 方法来触发。
    4. drawForeground: 绘制前景以及装饰，例如滚动条等。

### 硬绘与软绘

硬绘流程：

<img src="android/interview/view-mld/resources/mld_13.png" style="width:100%">

1. 记录绘制命令：
主线程遍历 View 树，生成 DisplayList（GPU 指令集合）。

2. 异步执行：
RenderThread 将 DisplayList 提交给 GPU。

3. GPU 渲染：
GPU 直接操作纹理，结果存入 GraphicBuffer。

4. 合成显示：
通过 SurfaceFlinger 合成到屏幕。


软绘流程：

<img src="android/interview/view-mld/resources/mld_14.png" style="width:100%">

1. 主线程绘制：
直接调用 View 的 draw() 方法，在 Canvas（关联 Bitmap）上绘制像素。

2. 内存拷贝：
将 Bitmap 数据拷贝到 Surface 的缓冲区。

3. 阻塞提交：
通过 Surface.unlockCanvasAndPost() 提交数据，可能阻塞主线程。
