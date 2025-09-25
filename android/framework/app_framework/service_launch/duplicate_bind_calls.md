# 重复绑定的思考

在 AMS 的 publishService 方法中看到这样的代码。

```java
    public void publishService(IBinder token, Intent intent, IBinder service) {
        //...

        synchronized(this) {
            //...
            ServiceRecord r = (ServiceRecord)token;

            //...
            if (r != null) {
                Intent.FilterComparison filter
                        = new Intent.FilterComparison(intent);
                IntentBindRecord b = r.bindings.get(filter);
                if (b != null && !b.received) {
                    b.binder = service;
                    b.requested = true;
                    b.received = true;
                    if (r.connections.size() > 0) {
                        Iterator<ArrayList<ConnectionRecord>> it
                                = r.connections.values().iterator();
                        while (it.hasNext()) {
                            ArrayList<ConnectionRecord> clist = it.next();
                            for (int i=0; i<clist.size(); i++) {
                                ConnectionRecord c = clist.get(i);
                                if (!filter.equals(c.binding.intent.intent)) {
                                    if (DEBUG_SERVICE) Slog.v(
                                            TAG, "Not publishing to: " + c);
                                    if (DEBUG_SERVICE) Slog.v(
                                            TAG, "Bound intent: " + c.binding.intent.intent);
                                    if (DEBUG_SERVICE) Slog.v(
                                            TAG, "Published intent: " + intent);
                                    continue;
                                }
                                if (DEBUG_SERVICE) Slog.v(TAG, "Publishing to: " + c);
                                try {
                                    c.conn.connected(r.name, service);
                                } catch (Exception e) {
                                    Slog.w(TAG, "Failure sending service " + r.name +
                                          " to connection " + c.conn.asBinder() +
                                          " (in " + c.binding.client.processName + ")", e);
                                }
                            }
                        }
                    }
                }

                serviceDoneExecutingLocked(r, mStoppingServices.contains(r));

                Binder.restoreCallingIdentity(origId);
            }
        }
    }
```

这里关注一个数据结构，ServiceRecord.connections, 其定义如下。以 InnerConnection 为 key，保存着一个 ConnectionRecord 列表。

```java
final HashMap<IBinder, ArrayList<ConnectionRecord>> connections
        = new HashMap<IBinder, ArrayList<ConnectionRecord>>();
```

为啥一个 InnerConnection 会对应一组 ConnectionRecord 呢？因为不同的 Activity 可能会使用同一个 connection 来与 service 建立连接。

只要你 connection 一样，在 LoadedApk 中就会对应同一个 InnerConnection，但是 每一次 startService 或者 bindService 都会在 AMS 中创建一个 ConnectionRecord。

所以最后就会形成 InnerConnection 和 ConnectionRecord 一对多的情形了。

然后引出我们的问题，正如我们之前提到的，在 server 组件启动后，会触发 AMS 的 publishService 方法，此时 AMS 将 server 组件的 binder 对象返回给应用组件。

但是我们看代码中，这里直接在遍历所有的 ConnectionRecord，并依次触发对应的 connect 远程调用，这个远程调用最终会执行 connection 的 onServiceConnected 方法。

那这里就会有两个问题了？

1. 如果客户端两个 Activity 使用同一个 connection 发起 bindService，此时 AMS 会有两个 ConnectionRecord，这会不会导致调用两次 onServiceConnected 方法？
2. 为啥 AMS 不做优化呢？既然这些 ConnectionRecord 对应的是同一个 InnerConnection，为啥不任选一个 ConnectionRecord 发起远程调用绑定呢？

## 会不会两次调用？

首先明确表示，AMS 那边确实会触发两次远程的 InnerConnection.connect 方法。这个 方法里面也会调用两次 doConnect 方法，但是最终不会触发两次 onServiceConnected 方法。

为什么呢？因为这里有一个锁，以及一个 mActiveConnections，在第一次 doConnected 的时候，因为 old == null 那就向下执行，最终调用 onServiceConnected 方法。

第二次再调过来，不好意思，old 不是 null 了，而且 old.binder == service 也满足，那此时就直接返回了。

```java
public void doConnected(ComponentName name, IBinder service) {
    ServiceDispatcher.ConnectionInfo old;
    ServiceDispatcher.ConnectionInfo info;

    synchronized (this) {
        old = mActiveConnections.get(name);
        if (old != null && old.binder == service) {
            // Huh, already have this one.  Oh well!
            return;
        }

        if (service != null) {
           //...
            try {
               //...
                mActiveConnections.put(name, info);
            } catch (RemoteException e) {
                //...
            }

        } else {
            // The named service is being disconnected... clean up.
            mActiveConnections.remove(name);
        }

        if (old != null) {
            old.binder.unlinkToDeath(old.deathMonitor, 0);
        }
    }

    // If there was an old service, it is not disconnected.
    if (old != null) {
        mConnection.onServiceDisconnected(name);
    }
    // If there is a new service, it is now connected.
    if (service != null) {
        mConnection.onServiceConnected(name, service);
    }
}
```

## 为何 AMS 允许这样做？

因为我们可能存在使用同一个 connection 绑定不同服务的场景。

就像下面这样，这样的话对于不同的 ConnectionRecord 虽然对应的 InnerConnection 还是同一个，但是获取的 server binder 不是同一个，所以 AMS 还是要原封不动的将 binder 遍历返回。


```java
private ServiceConnection mSharedConnection = new ServiceConnection() {
    private IMusicPlayerService mMusicService;
    private IDownloadService mDownloadService;
    @Override
    public void onServiceConnected(ComponentName name, IBinder service) {
        if (name.getClassName().equals(MusicPlayerService.class.getName())) {
            mMusicService = IMusicPlayerService.Stub.asInterface(service);
        } else if (name.getClassName().equals(DownloadService.class.getName())) {
            mDownloadService = IDownloadService.Stub.asInterface(service);
        }
    }
    @Override
    public void onServiceDisconnected(ComponentName name) {
        if (name.getClassName().equals(MusicPlayerService.class.getName())) {
            mMusicService = null;
        } else if (name.getClassName().equals(DownloadService.class.getName())) {
            mDownloadService = null;
        }
    }
};
// 在 Activity 中绑定
bindService(new Intent(this, MusicPlayerService.class), mSharedConnection, ...);
bindService(new Intent(this, DownloadService.class), mSharedConnection, ...);
```
