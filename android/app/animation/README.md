# Animation

## Tween 动画

View 动画又称为 Tween(补间) 动画，Tween 这个词来自于 `Between`, 含义在于给定动画的两端状态，系统会自动补全中间的状态。

这种动画的特点就是完全没有对 View 属性做变更，而是在绘制阶段通过计算直接更改 Canvas 的绘制内容而实现。

举一个极端的例子，假如你有一个按钮在屏幕上端，你添加了一个平移的 Tween 动画，将其挪到屏幕下方，此时你点击下方的 Button 是不会触发按钮的点击事件的，反而只有点击原位置才能触发。


### Tween 类层次

<img src="android/app/animation/resources/1.png" style="width:100%" >

这里有两个抽象簇，第一个是 `Animation` 负责实际的动画类型，还有一个 `Interpolator` 负责补间操作，即中间动画状态的计算。`Interpolator` 类有一个方法 `getInterpolation`，方法签名如下，其接收一个 [0, 1] 范围的输入值，返回一个结果，可以理解成一个 `y = f(x)` 在区间 0-1 的映射。

```java
/**
 * Maps a value representing the elapsed fraction of an animation to a value that represents
 * the interpolated fraction. This interpolated value is then multiplied by the change in
 * value of an animation to derive the animated value at the current elapsed animation time.
 *
 * @param input A value between 0 and 1.0 indicating our current point
 *        in the animation where 0 represents the start and 1.0 represents
 *        the end
 * @return The interpolation value. This value can be more than 1.0 for
 *         interpolators which overshoot their targets, or less than 0 for
 *         interpolators that undershoot their targets.
 */
float getInterpolation(float input);
```

### 基础使用

#### 定义自己的 Interpolation

```java
public class CustomViewInterpolator implements Interpolator {
    @Override
    public float getInterpolation(float input) {
        // input 范围：0 → 1（动画从开始到结束的进度）
        // 前20%进度：快速变化（0→0.8）
        if (input <= 0.2f) {
            return input * 4; // 0.2*4=0.8
        }
        // 中间60%进度：缓慢变化（0.8→0.9）
        else if (input <= 0.8f) {
            return 0.8f + (input - 0.2f) * (0.1f / 0.6f); // 仅增加0.1
        }
        // 最后20%进度：再次加速（0.9→1.0）
        else {
            return 0.9f + (input - 0.8f) * 0.5f; // 0.2*0.5=0.1，总1.0
        }
    }
}
```

#### 初始化 Animation 对象

```java
// 1. 创建 Alpha 动画：从完全透明（0）到完全不透明（1）
AlphaAnimation alphaAnimation = new AlphaAnimation(0f, 1f);

// 2. 应用自定义插值器
alphaAnimation.setInterpolator(new CustomViewInterpolator());
```

#### 启动动画

```java
// View view;
view.startAnimation(alphaAnimation);
```

### 源码分析

#### AlphaAnimation 初始化

这个初始化太简单了，只是从外部传入的数据初始化了内部的变量，这两个变量代表着初始 alpha 和结束状态的 alpha 值。

```java
public AlphaAnimation(float fromAlpha, float toAlpha) {
    mFromAlpha = fromAlpha;
    mToAlpha = toAlpha;
}
```

#### 设置差值器

使用外部的差值器初始化内部的 mInterpolator 成员。

```java
public void setInterpolator(TimeInterpolator interpolator) {
    mInterpolator = interpolator;
}
```

#### 启动动画

启动动画的逻辑很简单，就是存储 Animation 对象并将自身区域设置成 dirty，以触发重绘，进而确保动画更新。

```java
// View.java
public void startAnimation(Animation animation) {
    //...
    setAnimation(animation); // 设置动画
    //...
    invalidate(true); // 标记自己的区域需要重绘，因为现在有动画了，所以需要在下一帧触发 draw 流程。
}

public void setAnimation(Animation animation) {
    // 存储 animation 在成员 mCurrentAnimation
    mCurrentAnimation = animation;

    if (animation != null) {
        // 初始化动画状态
        // If the screen is off assume the animation start time is now instead of
        // the next frame we draw. Keeping the START_ON_FIRST_FRAME start time
        // would cause the animation to start when the screen turns back on
        if (mAttachInfo != null && mAttachInfo.mDisplayState == Display.STATE_OFF
                && animation.getStartTime() == Animation.START_ON_FIRST_FRAME) {
            animation.setStartTime(AnimationUtils.currentAnimationTimeMillis());
        }
        animation.reset();
    }
}
```

#### 动画执行

正如我们之前提过的，如果有需要的话，每一帧 Android 视图更新过程中会按照 Measure -> Layout -> Draw 的顺序进行，在我们 start 一个 Animation 后，invalidate 的作用就确保了下一帧肯定会执行 View 对应的 Draw 方法，而我们的 Tewwn 动画也是在 Draw 方法执行的过程中产生作用。

```java
    boolean draw(@NonNull Canvas canvas, ViewGroup parent, long drawingTime) {

        //...

        boolean more = false;
        //...

        Transformation transformToApply = null;
        boolean concatMatrix = false;
        //...
        // 获取 Animation 对象，就是之前 set 进来的那个
        final Animation a = getAnimation();
        if (a != null) {
            // 计算动画属性，计算的结果保存在 parent 的 ChildTransformation 中
            more = applyLegacyAnimation(parent, drawingTime, a, scalingRequired);
            // 是不是需要进行矩阵变化，啥时候需要矩阵变化，形态/位置发生变化就需要变换，否则，例如只是 alpha 发生变化，是不会需要矩阵变化的。
            concatMatrix = a.willChangeTransformationMatrix();
            if (concatMatrix) {
                mPrivateFlags3 |= PFLAG3_VIEW_IS_ANIMATING_TRANSFORM;
            }
            // 取出来当前帧变化的参数
            transformToApply = parent.getChildTransformation();
        } else {
            //...
        }

        concatMatrix |= !childHasIdentityMatrix;
        //...

        float alpha = drawingWithRenderNode ? 1 : (getAlpha() * getTransitionAlpha());
        if (transformToApply != null
                || alpha < 1
                || !hasIdentityMatrix()
                || (mPrivateFlags3 & PFLAG3_VIEW_IS_ANIMATING_ALPHA) != 0) {
            if (transformToApply != null || !childHasIdentityMatrix) {
                //...

                if (transformToApply != null) {
                    if (concatMatrix) {
                        //...
                        // 将动画的变化矩阵应用到 canvas 上
                        canvas.concat(transformToApply.getMatrix());
                        canvas.translate(transX, transY);
                        //...
                    }

                    float transformAlpha = transformToApply.getAlpha();
                    if (transformAlpha < 1) {
                        // 获取变化的 alpha 值，后面也会用在 canvas 上
                        alpha *= transformAlpha;
                        //...
                    }
                }
                //...
            }
            //...
        } 
        //...
        return more;
    }
```

我们看下核心方法 `applyLegacyAnimation` 的实现。

```java
    private boolean applyLegacyAnimation(ViewGroup parent, long drawingTime,
            Animation a, boolean scalingRequired) {
        //...
        final Transformation t = parent.getChildTransformation(); // 获取 parent 的 ChildTransformation 对象。
        boolean more = a.getTransformation(drawingTime, t, 1f); // 调用 animation 对象的 getTransformation 方法来计算 Transformation，计算结果存储在 t 中，也就是 parent 的 ChildTransformation 中。
        // 返回的 more 的意思是动画是不是还有后续。true 的话代表还有后续，false 代表动画已经结束。
        //...

        if (more) {
            // 这里先不管 willChangeBounds 的判断，我们可以看到的是只要动画还有后续，都会调用 invalidate 触发重绘制，目的就是确保下一帧的动画可以顺利被绘制。
            if (!a.willChangeBounds()) {
                //...
                    parent.invalidate(mLeft, mTop, mRight, mBottom);
                //...
            } else {
                //...
                parent.invalidate(left, top, left + (int) (region.width() + .5f),
                        top + (int) (region.height() + .5f));
            }
        }
        return more;
    }
```

我们再看一下 Animation 对象的 getTransformation 方法，这个方法中实实在在的进行了动画的计算，为了方便起见，我们以 AlphaAnimation 来展示。

这个函数在开始的时候计算出了一个 normalizedTime 用来作为动画参数计算的输入，随后以这个值调用了 getTransformationAt 方法计算动画参数。

```java
// Animation.java
    public boolean getTransformation(long currentTime, Transformation outTransformation) {
        //...
            getTransformationAt(normalizedTime, outTransformation);
        //...

        return mMore;
    }

    public void getTransformationAt(float normalizedTime, Transformation outTransformation) {
        //  通过回调我们差值器的 getInterpolation 方法进行参数修正
        final float interpolatedTime = mInterpolator.getInterpolation(normalizedTime);
        //  通过修正的参数计算动画参数
        applyTransformation(interpolatedTime, outTransformation);
    }

// AlphaAnimation.java
    protected void applyTransformation(float interpolatedTime, Transformation t) {
        // 获取 alpha 值的初始值
        final float alpha = mFromAlpha;
        // 进行计算 结果值 = 初始值 + 变化率 * 变化区间
        // 这里可以看出来，AlphaAnimation 这个函数是直线方程，最终结果的非直线关系来自于差值器。
        t.setAlpha(alpha + ((mToAlpha - alpha) * interpolatedTime));
    }

```

## 帧动画

帧动画本质是一个按照规定时间间隔自动切换的 Drawable 对象。

### 类继承层次

<img src="android/app/animation/resources/2.png" style="width:50%" >

这个图里，黄色的是抽象类，红色的是接口。

AnimationDrawable 实现了 Runnable 接口代表其可以作为一个 job 去执行。实现了 Animatable 接口，代表其可以被视为一个动画去执行。

### 基础使用方式

使用的基本方法就是我们将一个 AnimationDrawable 类型的资源设置为一个 View 的背景，随后对其调用 start 方法。

```java
var target = view.findViewById<View>(R.id.target)
target.setBackgroundResource(R.drawable.anim_frame)
val animationDrawable = target.background as AnimationDrawable
animationDrawable.start()
```

### 源码分析

我们首先来看 AnimationDrawable 类的 start 方法。

```java
public void start() {
    mAnimating = true;

    if (!isRunning()) {
        // 在一个没有 running 的动画被 start 的时候，将会从它的第一帧开始播放。
        // Start from 0th frame.
        setFrame(0, false, mAnimationState.getChildCount() > 1
                || !mAnimationState.mOneShot);
    }
}
```

然后我们看 `setFrame` 这个方法，这里传入三个参数，第一个 frame 代表设置的帧下标，unschedule 代表是不是停止动画，animate 代表是不是在播放当前帧后继续播放下一帧。

```java
private void setFrame(int frame, boolean unschedule, boolean animate) {
    // 如果范围大于总的帧数了，那就返回
    if (frame >= mAnimationState.getChildCount()) {
        return;
    }
    mAnimating = animate;
    mCurFrame = frame;
    // 选择对应的帧对应的资源并进行展示
    selectDrawable(frame);
    // 如果指定需要取消之前的调度，或者还需要播放下一帧，那就先取消当前的调度
    // 主要是为了避免多次的 schedule 带来混乱，所以需要把上一次的调度取消掉。
    if (unschedule || animate) {
        unscheduleSelf(this);
    }
    if (animate) {
        // 如果需要调度下一帧，那就 scheduleSelf 一次，为得是下一帧可以在未来被触发。
        // Unscheduling may have clobbered these values; restore them
        mCurFrame = frame;
        mRunning = true;
        scheduleSelf(this, SystemClock.uptimeMillis() + mAnimationState.mDurations[frame]);
    }
}
```

我们先看 `selectDrawable` 方法的实现，这个方法来自于基类 DrawableContainer。

```java
public boolean selectDrawable(int index) {
    if (index == mCurIndex) {
        return false;
    }
    //...
    // 如果设置了淡出
    if (mDrawableContainerState.mExitFadeDuration > 0) {
        // 这里面在计算淡出的时间等信息，暂时看不懂
        if (mLastDrawable != null) {
            mLastDrawable.setVisible(false, false);
        }
        if (mCurrDrawable != null) {
            mLastDrawable = mCurrDrawable;
            mLastIndex = mCurIndex;
            mExitAnimationEnd = now + mDrawableContainerState.mExitFadeDuration;
        } else {
            mLastDrawable = null;
            mLastIndex = -1;
            mExitAnimationEnd = 0;
        }
    } else if (mCurrDrawable != null) {
        // 没有设置淡出，就直接隐藏
        mCurrDrawable.setVisible(false, false);
    }

    if (index >= 0 && index < mDrawableContainerState.mNumChildren) {
        final Drawable d = mDrawableContainerState.getChild(index); // 获取新的一帧
        mCurrDrawable = d;
        //...
    } else {
        mCurrDrawable = null;
        mCurIndex = -1;
    }

    //...
    // 触发下一帧的重绘
    invalidateSelf();

    return true;
}
```

然后我们看 unscheduleSelf 方法的实现，这个 callback 是啥，这里直接给出答案，callback 就是使用到这个 Drawable 资源的 View 组件。这点从 View 类的声明就可以看出来。 ```public class View implements Drawable.Callback```。

```java
public void unscheduleSelf(@NonNull Runnable what) {
    final Callback callback = getCallback();
    if (callback != null) {
        // 调用到 View.unscheduleDrawable 方法。
        callback.unscheduleDrawable(this, what);
    }
}

// View.java
public void unscheduleDrawable(@NonNull Drawable who, @NonNull Runnable what) {
    if (verifyDrawable(who) && what != null) {
        if (mAttachInfo != null) {
            // 从 choregrpher 回调中移除
            mAttachInfo.mViewRootImpl.mChoreographer.removeCallbacks(
                    Choreographer.CALLBACK_ANIMATION, what, who);
        }
        // 从pending 队列中移除对应的 runnable
        // 这里之所以两个队列都尝试移除，因为不知道之前 schedule 的时候，到底放到那个队列了，所以干脆都移除一次。
        getRunQueue().removeCallbacks(what);
    }
}
```

同理我们看下 scheduleSelf 的实现，依然是触发 View.scheduleDrawable 方法。

```java
public void scheduleSelf(@NonNull Runnable what, long when) {
    final Callback callback = getCallback();
    if (callback != null) {
        callback.scheduleDrawable(this, what, when);
    }
}
// View.java
public void scheduleDrawable(@NonNull Drawable who, @NonNull Runnable what, long when) {
    if (verifyDrawable(who) && what != null) {
        final long delay = when - SystemClock.uptimeMillis();
        // 注册回调，会在下一次 vsync 到来的时候触发 AninmationDrawable 的 run 方法。
        if (mAttachInfo != null) {
            mAttachInfo.mViewRootImpl.mChoreographer.postCallbackDelayed(
                    Choreographer.CALLBACK_ANIMATION, what, who,
                    Choreographer.subtractFrameDelay(delay));
        } else {
            // Postpone the runnable until we know
            // on which thread it needs to run.
            getRunQueue().postDelayed(what, delay);
        }
    }
}
```

然后我们再看下 AnimationDrawable 的 run 方法的实现。 可以看到就是计算下一帧的下标，然后再一次调用 setFrame 方法。

```java
public void run() {
    nextFrame(false);
}

private void nextFrame(boolean unschedule) {
    int nextFrame = mCurFrame + 1;
    final int numFrames = mAnimationState.getChildCount();
    final boolean isLastFrame = mAnimationState.mOneShot && nextFrame >= (numFrames - 1);

    // Loop if necessary. One-shot animations should never hit this case.
    if (!mAnimationState.mOneShot && nextFrame >= numFrames) {
        nextFrame = 0;
    }

    setFrame(nextFrame, unschedule, !isLastFrame);
}
```

## 属性动画

属性动画的本质是给每个对象的属性提供按照 VSync 的节奏进行更新的能力。

### 类层次

<img src="android/app/animation/resources/3.png" style="width:100%" >

### 基础使用方式

下面展示了一个属性动画的基本使用方式。

```java
Button animateBtn = xxx;

// 针对于 Button 对象的 alpha 属性设置一个变化区间。
val alphaAnimator = ObjectAnimator.ofFloat(animateBtn, "alpha", 1f, 0.5f, 1f)
alphaAnimator.duration = 1000 // 动画时长1秒
// 启动动画
alphaAnimator.start()
```

### 源码分析

首先我们看 ofFloat 方法，这个操作将会创建一个 ObjectAnimator 对象，并对属性以及属性变化区间进行记录。

```java
// ObjectAnimator.java
public static ObjectAnimator ofFloat(Object target, String propertyName, float... values) {
    ObjectAnimator anim = new ObjectAnimator(target, propertyName); // 创建一个 ObjectAnimator 实例
    anim.setFloatValues(values);      // 设置属性值的变化序列
    return anim;
}

private ObjectAnimator(Object target, String propertyName) {
    setTarget(target);  // 设置属性变化的目标对象
    setPropertyName(propertyName); // 设置需要变化的属性名称
}

public void setTarget(@Nullable Object target) {
    //...
        mTarget = target;
        // New target should cause re-initialization prior to starting
        mInitialized = false;
    //...
}

/*
mValues 是一个 PropertyValuesHolder[] 数组，存储所有需要进行变化的属性信息。在 ObjectAnimator 的场景下，其实只有一个值，
因为 每一个 ObjectAnimator 只会对一个属性进行变化。所以这里也就是 mValues[0].

如果我们是第一次创建，mValues 是 null，所以这个函数只是将 propertyName 记录在了 mPropertyName 中，没有做其他的事情。
*/

public void setPropertyName(@NonNull String propertyName) {
    // mValues could be null if this is being constructed piecemeal. Just record the
    // propertyName to be used later when setValues() is called if so.
    // 第一次创建 ObjectAnimator 没有执行到。
    if (mValues != null) {
        PropertyValuesHolder valuesHolder = mValues[0];
        String oldName = valuesHolder.getPropertyName();
        valuesHolder.setPropertyName(propertyName);
        mValuesMap.remove(oldName);
        mValuesMap.put(propertyName, valuesHolder);
    }
    mPropertyName = propertyName;
    // New property/values/target should cause re-initialization prior to starting
    mInitialized = false;
}

// 然后我们看 setFloatValues。这个操作本质就是通过 mPropertyName 和 values 构造 PropertyValuesHolder 对象并保存在 mValues 中。

public void setFloatValues(float... values) {
    // 第一次 mValues 是 null
    if (mValues == null || mValues.length == 0) {
        // No values yet - this animator is being constructed piecemeal. Init the values with
        // whatever the current propertyName is
        if (mProperty != null) { // 不走这里
            setValues(PropertyValuesHolder.ofFloat(mProperty, values));
        } else {
            // 调用基类的 setValues 方法
            setValues(PropertyValuesHolder.ofFloat(mPropertyName, values));
        }
    } else {
        super.setFloatValues(values);
    }
}

// ValueAnimator.java
public void setValues(PropertyValuesHolder... values) {
    int numValues = values.length; // ObjectAnimator 场景下是 1
    mValues = values;   // [PropertyValuesHolder], 一个元素的 list
    mValuesMap = new HashMap<>(numValues);
    for (int i = 0; i < numValues; ++i) {
        PropertyValuesHolder valuesHolder = values[i];
        mValuesMap.put(valuesHolder.getPropertyName(), valuesHolder);
    }
    // New property/values/target should cause re-initialization prior to starting
    mInitialized = false;
}
```

随后我们看 start 方法。

```java
// ObjectAnimator.java
// 这个方法没有做太多事情，直接调用的基类的 start
public void start() {
    AnimationHandler.getInstance().autoCancelBasedOn(this);
    //...
    super.start();
}

// ValueAnimator.java
public void start() {
    start(false);
}

// ValueAnimator.java
// 这里有较多的逻辑，我们只关注 addAnimationCallback 这个操作，这也是动画可以连续播放的核心操作
private void start(boolean playBackwards) {
    if (Looper.myLooper() == null) {
        throw new AndroidRuntimeException("Animators may only be run on Looper threads");
    }
    mReversing = playBackwards;
    //...
    addAnimationCallback(0);

    //...
}
// ValueAnimator.java
// 因为每一个 Animator 都实现了 AnimationHandler.AnimationFrameCallback 接口，所以这里直接将自己注册到 AnimationHandler 中。
private void addAnimationCallback(long delay) {
    if (!mSelfPulse) {
        return;
    }
    getAnimationHandler().addAnimationFrameCallback(this, delay);
}
```

再进一步查看 addAnimationFrameCallback 逻辑前，我们看一下 AnimationHandler 的一个成员变量。

```java
// AnimationHandler.java
// 这个变量是一个 Choreographer.FrameCallback, 可以注册到 Choreographer 中，随后会在 VSync 带来后由 Choreographer 触发。
// 触发后，就执行里面的 doFrame 操作。
    private final Choreographer.FrameCallback mFrameCallback = new Choreographer.FrameCallback() {
        @Override
        public void doFrame(long frameTimeNanos) {
            doAnimationFrame(getProvider().getFrameTime());
            if (mAnimationCallbacks.size() > 0) {
                getProvider().postFrameCallback(this);
            }
        }
    };
```

然后我们看 addAnimationFrameCallback 操作。

```java
// AnimationHandler.java
public void addAnimationFrameCallback(final AnimationFrameCallback callback, long delay) {
    // 如果是第一次注册 callback，那就给 Choreographer 中注册一下上面提到的 FrameCallback
    if (mAnimationCallbacks.size() == 0) {
        getProvider().postFrameCallback(mFrameCallback);
    }
    // 在 mAnimationCallbacks 进行保存。
    if (!mAnimationCallbacks.contains(callback)) {
        mAnimationCallbacks.add(callback);
    }
    //...
}
```

到这里我们就 start 成功了，后面就等 VSync 到来后通过 mFrameCallback 的 doFrame 进一步执行了。

我们继续看这里面的 doAnimationFrame 方法，在这个操作里面会遍历刚才注册的 AnimationFrameCallback，也就是 ObjectAnimator 本身，并执行他们的 doAnimationFrame 方法。

```java
// AnimationHandler.java
private void doAnimationFrame(long frameTime) {
    long currentTime = SystemClock.uptimeMillis();
    final int size = mAnimationCallbacks.size();
    for (int i = 0; i < size; i++) {
        final AnimationFrameCallback callback = mAnimationCallbacks.get(i);
        if (callback == null) {
            continue;
        }
        if (isCallbackDue(callback, currentTime)) {
            callback.doAnimationFrame(frameTime);
            //...
        }
    }
    cleanUpList();
}
```

那我们再回去看看 doAnimationFrame 的内容。这个里面也是乱七八糟的一堆，但是核心逻辑就下面一行 animateBasedOnTime 按照当前时间执行对应的属性变化。animateBasedOnTime 中会依据传入的 currentTime 进一步计算一个 currentIterationFraction 值，交给 animateValue 进行属性最终值的计算。

```java
// ValueAnimator.java
    public final boolean doAnimationFrame(long frameTime) {
        //...
        final long currentTime = Math.max(frameTime, mStartTime);
        boolean finished = animateBasedOnTime(currentTime);

        //...
        return finished;
    }

    boolean animateBasedOnTime(long currentTime) {
        boolean done = false;
        if (mRunning) {
            //...
            mOverallFraction = clampFraction(fraction);
            float currentIterationFraction = getCurrentIterationFraction(
                    mOverallFraction, mReversing);
            animateValue(currentIterationFraction);
        }
        return done;
    }
```

到这里，我们得回去 ObjectAnimator 因为它重写了 animateValue 方法。我们可以看到很简单！就是遍历 PropertyValuesHolder[] 取出其中的每一个 PropertyValuesHolder 执行它的 setAnimatedValue 方法，传入的 target 就是我们需要变更属性的 object。也就是我们例子中提到的 Button。

```java
// ObjectAnimator.java
    void animateValue(float fraction) {
        final Object target = getTarget();
        super.animateValue(fraction); // 这里调用基类的 animateValue 方法，去完成具体属性值的计算。
        /*
            void animateValue(float fraction) {
                //...
                if (mValues == null) {
                    return;
                }
                // 通过差值器修正
                fraction = mInterpolator.getInterpolation(fraction);
                mCurrentFraction = fraction;
                int numValues = mValues.length;
                for (int i = 0; i < numValues; ++i) {
                    // 使用 PropertyValuesHolder 进行计算
                    mValues[i].calculateValue(fraction);
                }
                //...
            }
        */
        int numValues = mValues.length;
        for (int i = 0; i < numValues; ++i) {
            mValues[i].setAnimatedValue(target);
        }
    }
```

然后我们进入到 PropertyValuesHolder (FloatPropertyValuesHolder) 中，看 setAnimatedValue 的实现。

这个方法具体的内容就不说了，不管大概可以看得出来，或是调用对应对象的 set 方法进行设置，或者通过 jni 触发 c++，c++ 那边再进行属性设置。从而实现属性的变更。

```java
        void setAnimatedValue(Object target) {
            if (mFloatProperty != null) {
                mFloatProperty.setValue(target, mFloatAnimatedValue);
                return;
            }
            if (mProperty != null) {
                mProperty.set(target, mFloatAnimatedValue);
                return;
            }
            if (mJniSetter != 0) {
                nCallFloatMethod(target, mJniSetter, mFloatAnimatedValue);
                return;
            }
            if (mSetter != null) {
                try {
                    mTmpValueArray[0] = mFloatAnimatedValue;
                    mSetter.invoke(target, mTmpValueArray);
                } catch (InvocationTargetException e) {
                    Log.e("PropertyValuesHolder", e.toString());
                } catch (IllegalAccessException e) {
                    Log.e("PropertyValuesHolder", e.toString());
                }
            }
        }
```

到这里，我们完成了一轮属性的变化以及更新，那下一轮变化如何触发呢? 这就要回到我们 `Choreographer.FrameCallback` 的 `doFrame` 方法中。

```java
    private final Choreographer.FrameCallback mFrameCallback = new Choreographer.FrameCallback() {
        @Override
        public void doFrame(long frameTimeNanos) {
            doAnimationFrame(getProvider().getFrameTime());
            // 如果还有 callback，(在之前的场景，我们的 ObjectAnimator 都没有把自己 remove 掉，所以这里 size 不为 0)
            // 那就再次把自己添加到 Choreographer 的回调中，等待下一帧触发。
            // 这里也有人会有疑问，为什么每次都需要添加，因为 Choreographer 中的回调是一次性调用，调用完就移除。
            if (mAnimationCallbacks.size() > 0) {
                getProvider().postFrameCallback(this);
            }
        }
    };
```