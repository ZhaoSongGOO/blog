# Measure 深入分析


## measure

measure 方法是一个 final 方法，由 View 基类提供实现，所有的视图家族都使用同一份 measure。下面展示 View.measure 方法的核心逻辑(删除了一些边界逻辑)。主要步骤如下：

1. 依据父视图约束信息生成缓存 key

为什么要生成缓存，这是一种优化机制，主要是为了在父视图约束没有发生变化的时候避免对子视图进行重新测量。

缓存的数据类型是一个 map，其中的 key 来自于父视图约束编码的生成，value 是当前视图 measure 后的测量结果数据编码。

2. 获取 forceLayout 和 needsLayout 状态

- forceLayout 代表强制布局，一般在 RequestLayout 或者 setLayoutParams 后就会将 mPrivateFlags | PFLAG_FORCE_LAYOUT，从而设置成强制布局状态，因为这些操作一般都会修改视图内容或者尺寸，所以必须进行重新布局。

- needsLayout 代表是不是有必要布局，needsLayout 包含一些子条件。
    - specChanged: 父视图约束是否发生变化。
    - isSpecExactly: 父视图约束是不是 EXACTLY。
    - matchesSpecSize: 当前子视图已经和父视图约束已知。
    - sAlwaysRemeasureExactly: 系统设置永远对 EXACTLY 进行重新布局。

    这块的逻辑其实很精妙，我们按照顺序来理一下：
    - 如果父视图约束发生变化了，那就需要重新布局，否则下一步，
    - 如果系统设置永远对 EXACTLY 进行重新布局，否则下一步，
    - 如果系统没有设置永远对 EXACTLY 进行重新布局，但是当前约束不是 EXACTLY 约束就重新布局。否则下一步，
    - 如果是约束布局，但是当前视图尺寸和父约束不一致，那就需要重新布局。

    总结一下就是，父视图约束变了就需要重新布局，如果没变，但是父视图约束模式是 AT_MOST 和 UNSPECIFIED 就需要重新布局。对于 EXACTLY 模式，如果当前视图的尺寸和约束尺寸还不一致，那就需要重新布局。

3. 尺寸结果测量

要么强制更新，要么需要更新，才会进入尺寸测量步骤。

- 尝试获取布局结果缓存，
    - 如果系统设置了 `sUseMeasureCacheDuringForceLayoutFlagValue` 字面意思就是就算 forceLayout 也可以使用上次的布局缓存，估计是为了在低端机型上优化布局性能。
    - 否则的话，如果 forceLayout 就不能使用缓存，即 index 为 -1，否则的话尝试获取缓存。

- 触发测量过程
    - 如果查找到缓存 cacheIndex >= 0，那就直接从缓存取数据，并设置到 View 的测量结果上，`setMeasuredDimensionRaw`。
    - 没有找到缓存的话，就调用自己的 `onMeasure` 方法来完成测量。

- 测量状态判断
    我们在自定义 View 开发中都知道，如果我们重写了 `onMeasure` 方法，且没有调用 `super.onMeasure` 那必须显式的调用 `setMeasuredDimension` 来设置我们的测量结果。否则将会触发异常 `IllegalStateException`。

4. 缓存测量结果

- 存储父视图约束信息，以便于下次比较。
- 存储本次测量结果，形成缓存。



```java
//View.java
public final void measure(int widthMeasureSpec, int heightMeasureSpec) {
    //1. 依据父视图约束信息生成缓存 key
    long key = (long) widthMeasureSpec << 32 | (long) heightMeasureSpec & 0xffffffffL;
    if (mMeasureCache == null) mMeasureCache = new LongSparseLongArray(2);

    //2. 获取 forceLayout 和 needsLayout 状态
    final boolean forceLayout = (mPrivateFlags & PFLAG_FORCE_LAYOUT) == PFLAG_FORCE_LAYOUT;
    final boolean specChanged = widthMeasureSpec != mOldWidthMeasureSpec
            || heightMeasureSpec != mOldHeightMeasureSpec;
    final boolean isSpecExactly = MeasureSpec.getMode(widthMeasureSpec) == MeasureSpec.EXACTLY
            && MeasureSpec.getMode(heightMeasureSpec) == MeasureSpec.EXACTLY;
    final boolean matchesSpecSize = getMeasuredWidth() == MeasureSpec.getSize(widthMeasureSpec)
            && getMeasuredHeight() == MeasureSpec.getSize(heightMeasureSpec);
    final boolean needsLayout = specChanged
            && (sAlwaysRemeasureExactly || !isSpecExactly || !matchesSpecSize);

    //3. 尺寸结果测量
    if (forceLayout || needsLayout) {
        int cacheIndex;
        if (sUseMeasureCacheDuringForceLayoutFlagValue) {
            cacheIndex =  mMeasureCache.indexOfKey(key);
        } else {
            cacheIndex = forceLayout ? -1 : mMeasureCache.indexOfKey(key);
        }

        if (cacheIndex < 0) {
            // measure ourselves, this should set the measured dimension flag back
            onMeasure(widthMeasureSpec, heightMeasureSpec);
        } else {
            long value = mMeasureCache.valueAt(cacheIndex);
            // Casting a long to int drops the high 32 bits, no mask needed
            setMeasuredDimensionRaw((int) (value >> 32), (int) value);
        }

        if ((mPrivateFlags & PFLAG_MEASURED_DIMENSION_SET) != PFLAG_MEASURED_DIMENSION_SET) {
            throw new IllegalStateException("View with id " + getId() + ": "
                    + getClass().getName() + "#onMeasure() did not set the"
                    + " measured dimension by calling"
                    + " setMeasuredDimension()");
        }

        mPrivateFlags |= PFLAG_LAYOUT_REQUIRED;
    }
    //4. 缓存测量结果
    mOldWidthMeasureSpec = widthMeasureSpec;
    mOldHeightMeasureSpec = heightMeasureSpec;

    mMeasureCache.put(key, ((long) mMeasuredWidth) << 32 |
            (long) mMeasuredHeight & 0xffffffffL); // suppress sign extension
}
```

## onMeasure

### [TextView](android/app/view-mld/measure/textview-measure.md)