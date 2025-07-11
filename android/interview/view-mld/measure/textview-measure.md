# TextView measure

## onMeasure

从 measure 的讲解可以看出，measure 的主要测量过程主要是放在 onMeasure 中，下面我们以 TextView 为目标研究一下它的 onMeasure 方法。内容非常多，涉及多方对象协同，但是不要害怕，就把他当成你自己实现的一个 View 即可。

### 初始化一些变量

首先，解析父视图布局参数用于后面使用，然后初始化两个变量 width 和 height，这个就是后面 TextView 测绘出来的宽高数据。

随后初始化了一个 boring 和 hintboring 两个变量，这里需要解释下什么是 boring 和 hint。

boring 意思是无聊的，在这里的意思指的是一个非常平凡普通的文本。对于不换行、不包含表情的文本都是普通文本，对于这种简单文本，将采用更轻量的文本排版方式 BoringLayout。

hint 的意思是提示词，即在你 TextView 没有内容的时候显示的提示词，这个提示词也需要区分是不是普通文本。

随后 mTextDir 代表的是排版方向，RTL 还是 LTR。

```java
// 解析父视图布局参数
int widthMode = MeasureSpec.getMode(widthMeasureSpec);
int heightMode = MeasureSpec.getMode(heightMeasureSpec);
int widthSize = MeasureSpec.getSize(widthMeasureSpec);
int heightSize = MeasureSpec.getSize(heightMeasureSpec);

// TextView 测量结果初始化
int width;
int height;

// 
BoringLayout.Metrics boring = UNKNOWN_BORING;
BoringLayout.Metrics hintBoring = UNKNOWN_BORING;

if (mTextDir == null) {
    mTextDir = getTextDirectionHeuristic();
}
//....
```

### 测量宽度

随后先测量宽度，整体来看，宽度计算必高度计算复杂太多了，因为文本排版基本都是横向进行的，因此先将宽度确定好后，高度自然就确定了。

先进行一次判断，如果父视图的约束模式是 EXACTLY，那就直接用，别测量了。

```java
if (widthMode == MeasureSpec.EXACTLY) {
    // Parent has told us how big to be. So be it.
    width = widthSize;
} else {
    // 测量宽度
}

```

真正需要重新测量的话，步骤如下。

1. 首先看 mLayout 是不是空，不是空的话，就尝试获取 mLayout 的布局结果。

```java
if (mLayout != null && mEllipsize == null) {
    des = desired(mLayout, mUseBoundsForWidth);
}
```

mLayout 是啥？就是之前提到的文本排版引擎 BoringLayout 或者 StaticLayout(复杂文本排版)。

那什么时候 mLayout 会是空呢? 一般在文本内容被重新设置，文本属性变化以及强制 requestLayout 的时候，都会被设置成 null。

2. 第一次尝试测量

如果第一步 des 失败，会返回 -1，这里就像尝试用 BoringLayout(尝试的意思是不管文本是不是 boring，都试一下，大不了失败) 去进行测量，否则的话，使用 des，并将 fromexisting 置为 true，表示使用之前的计算结果。

```java
if (des < 0) {
    boring = BoringLayout.isBoring(mTransformed, mTextPaint, mTextDir,
            isFallbackLineSpacingForBoringLayout(), getResolvedMinimumFontMetrics(),
            mBoring);
    if (boring != null) {
        mBoring = boring;
    }
} else {
    fromexisting = true;
}
```

3. 第二次尝试

在上面我们首先尝试了使用已有的布局结果，失败后又尝试直接获取 BoringLayout 的结果，随后进行第三次尝试。

如果 boring 结果是空的，即不是 boring 文本，那就调用 Layout.getDesiredWidthWithLimit 获取宽度结果，这个方法是 Layout 的静态方法，也是 StaticLayout 的宽度测算方案。

需要知道的是，这里的 getDesiredWidthWithLimit 只是快速的得到实际的宽度，而没有进行文本排版操作。

如果 上一步的 boring 有结果，那就使用 boring 结果。

```java
if (boring == null || boring == UNKNOWN_BORING) {
    if (des < 0) {
        des = (int) Math.ceil(Layout.getDesiredWidthWithLimit(mTransformed, 0,
                mTransformed.length(), mTextPaint, mTextDir, widthLimit,
                mUseBoundsForWidth));
    }
    width = des;
} else {
    if (mUseBoundsForWidth) {
        RectF bbox = boring.getDrawingBoundingBox();
        float rightMax = Math.max(bbox.right, boring.width);
        float leftMin = Math.min(bbox.left, 0);
        width = Math.max(boring.width, (int) Math.ceil(rightMax - leftMin));
    } else {
        width = boring.width;
    }
}
```

4. 考虑 drawable 和 边界

上面都是在计算文本本身内容的尺寸，对于一个 TextView 来说，还需要考虑 

- drawle 内容的尺寸以及边界
- MinWidth 的最小限制
- 父视图最大尺寸限制


```java
final Drawables dr = mDrawables;
if (dr != null) {
    width = Math.max(width, dr.mDrawableWidthTop);
    width = Math.max(width, dr.mDrawableWidthBottom);
}

width += getCompoundPaddingLeft() + getCompoundPaddingRight();

width = Math.max(width, getSuggestedMinimumWidth());

if (widthMode == MeasureSpec.AT_MOST) {
    width = Math.min(widthSize, width);
}
```

5. 需要的话，初始化文本布局引擎 mLayout

上面提到了，在我们对文本属性做更改后，会导致 mLayout 被设置成 null，此时我们就需要重新初始化 mLayout 引擎。

makeNewLayout 方法会依据文本是不是 boring，返回对应的 Layout。

此时还需要注意的是，在初始化 Layout 的过程中，会真正完成对文字的排版。

```java
if (mLayout == null) {
    makeNewLayout(want, hintWant, boring, hintBoring,
                    width - getCompoundPaddingLeft() - getCompoundPaddingRight(), false);
} 
```

### 测量高度

上面我们已经完成了宽度的测量，同时初始化了 mLayout，且在 mLayout 构造阶段进行了排版任务，现在就可以正式的获取高度了。

一样的，如果父视图设置固定的子视图高度，那就直接使用，否则，调用 getDesiredHeight 获取文字排版的高度，这个方法中会从刚才完成排版的 mLayout 中获取排版高度结果。

```java
if (heightMode == MeasureSpec.EXACTLY) {
    // Parent has told us how big to be. So be it.
    height = heightSize;
} else {
    int desired = getDesiredHeight();

    height = desired;
    mDesiredHeightAtMeasure = desired;

    if (heightMode == MeasureSpec.AT_MOST) {
        height = Math.min(desired, heightSize);
    }
}
```
