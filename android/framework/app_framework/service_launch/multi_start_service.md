# 重复启动服务

前面我们描述的都是 service 组件第一次被启动的场景，这样不可避免的对应的进程需要创建 service 实例，并触发其 onCreate 方法。
那假如用户使用了两次 startActivity 来操作同一个 service 组件，系统是如何避免 service 实例被重复创建呢？

在 AMS 中，不管是 bindService 还是 startService 都会触发 bringUpServiceLocked 的调用，如果这个 service 之前已经被创建了，那他的 app 以及 app.thread 不是 null，这里只进行 sendServiceArgsLocked 操作，就直接返回了，不会再次触发 service 实例的创建。

> sendServiceArgsLocked 这个里面就是触发 service 组件 onStartCommand 回调的执行。


```java
    private final boolean bringUpServiceLocked(ServiceRecord r,
            int intentFlags, boolean whileRestarting) {
        //Slog.i(TAG, "Bring up service:");
        //r.dump("  ");

        if (r.app != null && r.app.thread != null) {
            sendServiceArgsLocked(r, false);
            return true;
        }
        //...
    }
```