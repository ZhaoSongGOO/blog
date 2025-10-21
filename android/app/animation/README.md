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








