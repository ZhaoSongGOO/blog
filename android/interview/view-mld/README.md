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

## Layout 启动！

## Draw 启动！
