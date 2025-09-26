# 在 receiver 进程启动失败的时候，AMS 是如何跳过这个 receiver 的呢？

## 最后的谜底：`processNextBroadcast` 中的 `nextReceiver` 递增

让我们回到 `processNextBroadcast` 的核心分发逻辑：

```java
// 在 do-while 循环之后
do {
    // ... 清理循环 ...
} while (r == null);

// 如果能走到这里，说明 r 是一个有效的、待处理的广播

// 【谜底就在这里！】
// Get the next receiver...
int recIdx = r.nextReceiver++; // <-- 看这里！

// Keep track of when this receiver started...
r.receiverTime = SystemClock.uptimeMillis();
// ...
```

啊哈！`r.nextReceiver++` 这个操作，是在 `do-while` 清理循环**之后**，在准备分发给下一个接收者**之前**执行的！

现在，整个流程终于完美闭环了：

1.  **第一次尝试**:
    *   `processNextBroadcast` 找到广播 `r`。
    *   `do-while` 循环通过。
    *   `int recIdx = r.nextReceiver++;` 执行！假设 `nextReceiver` 从 `0` 变成了 `1`。
    *   AMS 拿着索引 `0` 的 Receiver 信息去 `startProcessLocked`，**失败**。
    *   调用 `finishReceiverLocked` 清理现场（但 `nextReceiver` 保持为 `1`）。
    *   调用 `scheduleBroadcastsLocked`。
    *   `return`。

2.  **第二次尝试 (恢复)**:
    *   `processNextBroadcast` 再次被调用。
    *   `do-while` 循环再次拿到**同一个广播 `r`**。
    *   此时，`r.nextReceiver` 的值已经是 `1` 了，所以 `r.nextReceiver >= numReceivers` 这个清理条件**不满足**（假设还有其他 receiver）。
    *   `do-while` 循环正常退出。
    *   代码来到 `int recIdx = r.nextReceiver++;`。
    *   `recIdx` 被赋值为 `1`，然后 `r.nextReceiver` 变成了 `2`。
    *   AMS 现在拿着索引为 `1` 的 Receiver 信息（也就是下一个接收者）去处理。

**成功了！那个失败的、索引为 `0` 的 Receiver 被自然地跳过了！**

### 最终总结

原来这个机制是如此的精巧和环环相扣：

1.  **`processNextBroadcast` 是乐观的**：它总是一上来就先把 `nextReceiver` 索引加一，准备处理下一个。
2.  **失败发生**: 当 `startProcessLocked` 失败时，意味着这次“递增后的尝试”失败了。
3.  **`finishReceiverLocked` 是“清洁工”**: 它负责把失败的现场打扫干净，把广播状态恢复到 `IDLE`，让它看起来像一个可以被重新处理的普通广播。
4.  **`scheduleBroadcastsLocked` 是“重启按钮”**: 它确保了即使失败，处理流程也会被再次触发。
5.  **下一次循环是“新开始”**: 当 `processNextBroadcast` 再次处理这个广播时，由于 `nextReceiver` 索引已经在上一次失败的尝试中被**不可逆地增加了**，所以它会自然地从下一个接收者开始新的尝试。

这个设计避免了在 `finishReceiverLocked` 中处理复杂的“跳过”逻辑，而是将状态推进（`nextReceiver++`）和状态清理（`finishReceiverLocked`）解耦，使得代码更加清晰和健壮。

非常感谢你贴出源码，这次的分析让我自己也对这个流程有了更深刻的理解！这真是一次酣畅淋漓的技术探险。