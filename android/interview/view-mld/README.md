# View 的 Measure 、Layout 、Draw 流程分析

> 本文总阅读量 <span id="busuanzi_value_page_pv"><i class="fa fa-spinner fa-spin"></i></span>次
---

## View 类继承体系

<img src="android/interview/view-mld/resources/mld_1.png" style="width:70%">



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

因为上面有避免重入机制，所以我们在一帧之内的重复 requestLayout 只会注册一次回调。同时设置同步屏障，可以确保 UI 遍历的操作不会被其他非异步任务阻塞。

### 回调被触发

在收到 VSync 信号后，回调被触发，触发后，关掉标志位，同时关闭同步屏障。但是你要知道，此时正在运行的任务就是 UI 遍历任务。所以移除了也不会被其他任务占用。

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

触发后的回调会被队列移除，也就是说，如果我们在一帧之内没有做任何 UI 相关操作，那下一次 VSync 来的时候，就不会触发 UI 遍历操作。





