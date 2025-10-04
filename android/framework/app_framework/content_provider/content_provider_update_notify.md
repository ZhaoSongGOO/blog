# Content Provider 数据更新通知

由于 Content Provider 组件中的数据是可以在不同的应用程序之间进行共享的，因此，这里就会存在一个数据一致性问题，即当一个应用程序更新 Content Provider 组件中的一个数据时，如何保证其他应用程序可以看到这个数据更新，以便保证所有的应用程序获得的共享数据都是最新的，并且是一致的。

Content Provider 组件的数据更新通知机制类似于 Android 系统的广播机制，它们都是一种消息发布和订阅的事件驱动模型。

在 Content Provider 组件的数据更新通知机制中，内容观察者(Content Observer)负责接收数据更新通知，而 Content Provider 组件负责发送数据更新通知。

内容观察者在接收数据更新通知之前，必须要先注册到 ContentService 中，并且告诉 ContentService 它要接收什么样的数据更新通知。这是通过一个 URI 来描述的。当 Content Provider 组件中的数据发生更新时，Content Provider 组件就会将用来描述这个数据的一个 URI 发送给 ContentService，以便 ContentService 可以找到与这个 URI 对应的内容观察者，最后向它们发送一个数据更新通知。

## 注册内容观察者

### Step1: 编写 ContentObserver

我们需要继承 ContentObserver 来实现我们自己的 ContentObserver。

```java
// MySmsObserver.java
import android.database.ContentObserver;
import android.net.Uri;
import android.os.Handler;
import android.util.Log;

// 1. 继承 ContentObserver
public class MySmsObserver extends ContentObserver {

    private static final String TAG = "MySmsObserver";

    /**
     * 构造函数是必须的。
     * @param handler A handler to run the onChange(boolean) method on.
     *                一个 Handler 对象，onChange() 方法会在此 Handler 关联的线程上被调用。
     *                如果传 null，则会使用默认的主线程 Handler。
     */
    public MySmsObserver(Handler handler) {
        super(handler);
    }

    /**
     * 当观察到的 Uri 发生变化时，此方法被调用。
     * 这是旧版的回调方法，在 API 16 之前使用。
     */
    @Override
    public void onChange(boolean selfChange) {
        super.onChange(selfChange);
        Log.d(TAG, "数据库发生了变化 (旧版回调)... selfChange = " + selfChange);
        // 通常我们会在新版的回调中处理逻辑
    }

    /**
     * 当观察到的 Uri 发生变化时，此方法被调用。
     * 这是从 API 16 (Android 4.1) 开始推荐使用的新版回调。
     * @param selfChange 如果是由我们自己的应用修改数据导致的通知，则为 true。
     * @param uri        发生变化的具体数据的 Uri。如果为 null，表示可能多个数据发生了变化。
     */
    @Override
    public void onChange(boolean selfChange, Uri uri) {
        super.onChange(selfChange, uri);
        
        Log.d(TAG, "数据库发生了变化 (新版回调)...");
        Log.d(TAG, "selfChange = " + selfChange);
        Log.d(TAG, "变化的 URI = " + uri);

        // 关键逻辑：判断是否是我们关心的短信收件箱的 URI
        // "content://sms/raw" 是收到短信时系统最先插入数据的地方
        // "content://sms/inbox" 是短信进入收件箱的 URI
        if (uri != null && uri.toString().contains("content://sms")) {
            Log.d(TAG, "检测到短信数据库变化！可能是新短信来了！");
            
            // 在这里，你可以执行读取最新短信的操作
            // 注意：这个 onChange 方法可能在短时间内被多次调用，
            // 需要做防抖处理，并且不要在这里执行耗时操作。
            // 最好是通过 Handler 发送消息到工作线程去处理。
        }
    }
}
```

### Step2: 初始化并注册 Observer

```java
MySmsObserver observer = new MySmsObserver(new Handler());
getContentResolver().registerContentObserver(URI, true, observer);
```

### Step3: ContentResolver.registerContentObserver

这里就先通过 observer.getContentObserver() 获取 ContentObserver 内部的一个 binder 本地对象，然后通过 SM 拿到 ContentService 的 binder 代理对象，发起跨进程调用 registerContentObserver。

```java
    public final void registerContentObserver(Uri uri, boolean notifyForDescendents,
            ContentObserver observer)
    {
        try {
            getContentService().registerContentObserver(uri, notifyForDescendents,
                    observer.getContentObserver());
        } catch (RemoteException e) {
        }
    }

    public static IContentService getContentService() {
        if (sContentService != null) {
            return sContentService;
        }
        IBinder b = ServiceManager.getService(CONTENT_SERVICE_NAME);
        if (Config.LOGV) Log.v("ContentService", "default service binder = " + b);
        sContentService = IContentService.Stub.asInterface(b);
        if (Config.LOGV) Log.v("ContentService", "default service = " + sContentService);
        return sContentService;
    }
```

### Step4: ContentObserver.getContentObserver

没什么多说的，就是返回了一个 Transport 对象，这个对象是一个 binder 实体对象。

```java
    public IContentObserver getContentObserver() {
        synchronized(lock) {
            if (mTransport == null) {
                mTransport = new Transport(this);
            }
            return mTransport;
        }
    }

    private static final class Transport extends IContentObserver.Stub {
        ContentObserver mContentObserver;

        public Transport(ContentObserver contentObserver) {
            mContentObserver = contentObserver;
        }

        public boolean deliverSelfNotifications() {
            ContentObserver contentObserver = mContentObserver;
            if (contentObserver != null) {
                return contentObserver.deliverSelfNotifications();
            }
            return false;
        }

        public void onChange(boolean selfChange) {
            ContentObserver contentObserver = mContentObserver;
            if (contentObserver != null) {
                contentObserver.dispatchChange(selfChange);
            }
        }

        public void releaseContentObserver() {
            mContentObserver = null;
        }
    }
```

### Step5: ContentService.registerContentObserver

```java
    public void registerContentObserver(Uri uri, boolean notifyForDescendents,
            IContentObserver observer) {
        if (observer == null || uri == null) {
            throw new IllegalArgumentException("You must pass a valid uri and observer");
        }
        // mRootNode =  new ObserverNode("");
        synchronized (mRootNode) {
            mRootNode.addObserverLocked(uri, observer, notifyForDescendents, mRootNode);
            //...
        }
    }
```

### Step6: ObserverNode.addObserverLocked

ContentService 在内部使用一个 ObserverNode 对象来保存一组监控相同数据的内容观察者，而每一个内容观察者都被封装成一个 ObserverEntry 对象保存在对应的 ObserverNode 对象的成员变量 mObservers 中。

一个内容观察者所要监控的数据是使用一个 URI 来描述的。假设有两个内容观察者 O1 和 O2，它们分别保存在 ObserverNode 对象 N1 和 N2 中，并且内容观察者 O2 所要监控的数据的 URI 是以内容观察者 O1 所要监控的数据的 URI 为前缀的，那么在 ContentService 中，ObserverNode 对象 N2 就会保存在 ObserverNode 对象 N1 的成员变量 mChildren 中，表示 ObserverNode 对象 N2 是 ObserverNode 对象 N1 的一个子节点。ContentService 就是通过这种形式将所有注册到它里面的内容观察者组织成一棵树的。

在 ContentService 中，每一个 ObserverNode 对象都有一个名称，保存在它的成员变量 mName 中。继续以上面的 ObserverNode 对象 N1 和 N2 为例，假设保存在它们里面的内容观察者所要监控的数据的 URI 分别为 "content：//my-authority" 和 "content：//my-authority/item"​，那么 ObserverNode 对象 N1 和 N2 的名称就分别为 "my-authority" 和 "item"​。

也就是说以 URI 的 path 关系来组织父子节点。

```java
        public void addObserverLocked(Uri uri, IContentObserver observer,
                boolean notifyForDescendents, Object observersLock) {
            addObserverLocked(uri, 0, observer, notifyForDescendents, observersLock);
        }

        private void addObserverLocked(Uri uri, int index, IContentObserver observer,
                boolean notifyForDescendents, Object observersLock) {
            // If this is the leaf node add the observer
            if (index == countUriSegments(uri)) {
                mObservers.add(new ObserverEntry(observer, notifyForDescendents, observersLock));
                return;
            }

            // Look to see if the proper child already exists
            String segment = getUriSegment(uri, index);
            if (segment == null) {
                throw new IllegalArgumentException("Invalid Uri (" + uri + ") used for observer");
            }
            int N = mChildren.size();
            for (int i = 0; i < N; i++) {
                ObserverNode node = mChildren.get(i);
                if (node.mName.equals(segment)) {
                    node.addObserverLocked(uri, index + 1, observer, notifyForDescendents, observersLock);
                    return;
                }
            }

            // No child found, create one
            ObserverNode node = new ObserverNode(segment);
            mChildren.add(node);
            node.addObserverLocked(uri, index + 1, observer, notifyForDescendents, observersLock);
        }
```

## 发送数据更新通知

在我们的 provider 知道数据发生更新的时候，例如有的 client 调用了 insert 方法插入了新的数据，我们可以在 provider 中利用 contentResolver 来发送数据更新通知。

Content Provider 组件首先会将数据更新通知发送给 ContentService，然后由 ContentService 将这个数据更新通知转发给目标内容观察者。

### Step1: ContentResolver.notifyChange


```java
    /**
     * Notify registered observers that a row was updated.
     * To register, call {@link #registerContentObserver(android.net.Uri , boolean, android.database.ContentObserver) registerContentObserver()}.
     * By default, CursorAdapter objects will get this notification.
     *
     * @param uri
     * @param observer The observer that originated the change, may be <code>null</null>
     */
    public void notifyChange(Uri uri, ContentObserver observer) {
        notifyChange(uri, observer, true /* sync to network */);
    }

    /**
     * Notify registered observers that a row was updated.
     * To register, call {@link #registerContentObserver(android.net.Uri , boolean, android.database.ContentObserver) registerContentObserver()}.
     * By default, CursorAdapter objects will get this notification.
     *
     * @param uri
     * @param observer The observer that originated the change, may be <code>null</null>
     * @param syncToNetwork If true, attempt to sync the change to the network.
     */
    public void notifyChange(Uri uri, ContentObserver observer, boolean syncToNetwork) {
        try {
            getContentService().notifyChange(
                    uri, observer == null ? null : observer.getContentObserver(),
                    observer != null && observer.deliverSelfNotifications(), syncToNetwork);
        } catch (RemoteException e) {
        }
    }
```

### Step2: ContentService.notifyChange

```java
    public void notifyChange(Uri uri, IContentObserver observer,
            boolean observerWantsSelfNotifications, boolean syncToNetwork) {
        //...
        try {
            ArrayList<ObserverCall> calls = new ArrayList<ObserverCall>();
            synchronized (mRootNode) {
                // 搜集观察者，即这次更改需要通知那些观察者
                mRootNode.collectObserversLocked(uri, 0, observer, observerWantsSelfNotifications,
                        calls);
            }
            final int numCalls = calls.size();
            for (int i=0; i<numCalls; i++) {
                ObserverCall oc = calls.get(i);
                try {
                    // 调用对应的 onChange 方法发送通知。
                    oc.mObserver.onChange(oc.mSelfNotify);
                    //...
                } catch (RemoteException ex) {
                    //...
                }
            }
            //...
        } finally {
            //...
        }
    }
```

### Step3: ObserverNode.collectObserversLocked

```java
        private void collectMyObserversLocked(boolean leaf, IContentObserver observer,
                boolean selfNotify, ArrayList<ObserverCall> calls) {
            int N = mObservers.size();
            IBinder observerBinder = observer == null ? null : observer.asBinder();
            for (int i = 0; i < N; i++) {
                ObserverEntry entry = mObservers.get(i);

                // Don't notify the observer if it sent the notification and isn't interesed
                // in self notifications
                if (entry.observer.asBinder() == observerBinder && !selfNotify) {
                    continue;
                }

                // Make sure the observer is interested in the notification
                if (leaf || (!leaf && entry.notifyForDescendents)) {
                    calls.add(new ObserverCall(this, entry.observer, selfNotify));
                }
            }
        }
        public void collectObserversLocked(Uri uri, int index, IContentObserver observer,
                boolean selfNotify, ArrayList<ObserverCall> calls) {
            String segment = null;
            int segmentCount = countUriSegments(uri);
            if (index >= segmentCount) {
                // This is the leaf node, notify all observers
                collectMyObserversLocked(true, observer, selfNotify, calls);
            } else if (index < segmentCount){
                segment = getUriSegment(uri, index);
                // Notify any observers at this level who are interested in descendents
                collectMyObserversLocked(false, observer, selfNotify, calls);
            }

            int N = mChildren.size();
            for (int i = 0; i < N; i++) {
                ObserverNode node = mChildren.get(i);
                if (segment == null || node.mName.equals(segment)) {
                    // We found the child,
                    node.collectObserversLocked(uri, index + 1, observer, selfNotify, calls);
                    if (segment != null) {
                        break;
                    }
                }
            }
        }
```

### Step4: Transport.onChange

```java
public void onChange(boolean selfChange) {
            ContentObserver contentObserver = mContentObserver;
            if (contentObserver != null) {
                contentObserver.dispatchChange(selfChange);
            }
        }
```

### Step5: ContentObserver.dispatchChange

NotificationRunnable 这个 runnable 对象的 run 方法后续会在主线程调用。

```java
    public final void dispatchChange(boolean selfChange) {
        if (mHandler == null) {
            onChange(selfChange);
        } else {
            mHandler.post(new NotificationRunnable(selfChange));
        }
    }
```

### Step6: NotificationRunnable.run

触发我们自己的 observer 的 onChange 回调。

```java
    private final class NotificationRunnable implements Runnable {

        private boolean mSelf;

        public NotificationRunnable(boolean self) {
            mSelf = self;
        }

        public void run() {
            ContentObserver.this.onChange(mSelf);
        }
    }
```



