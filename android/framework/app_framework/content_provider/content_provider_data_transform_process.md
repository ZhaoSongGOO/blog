# Content Provider 数据传输过程

一次数据传输过程过程大概分为下面几步。

1. client 组件通过 Articles.CONTENT_POS_URI 在当前应用程序进程中获得用来访问 provider 组件的一个 Binder 代理对象。
2. client 组件通过上一步获得的 Binder 代理对象来请求 provider 组件返回一个指定位置值的博客文章条目。
3. provider 组件创建一个 SQLiteCursor 对象，用来从内部的 SQLite 数据库中获得一个指定位置值的博客文章条目，然后将这个 SQLiteCursor 对象封装成一个 CursorToBulkCursorAdaptor 对象，以便可以传递给 client 组件。
4. provider 组件将上一步创建的 CursorToBulkCursorAdaptor 对象返回给 client 组件之前，发现 client 组件需要获得它所请求的博客文章信息的元数据，因此，provider 组件就会执行保存在上一步所创建的 SQLiteCursor 对象内部的一个数据库查询计划，以便可以获得 client 组件所请求的博客文章信息的元数据。

下面展示了一个使用 provider 获取数据的例子，我们就以这个例子为主线，分析每一步的步骤。

```java
public class ArticlesAdapter {
    private ContentResolver resolver = null;

    public ArticlesAdapter(Context context){
        resolver=context.getContentResolver();
    }
    public Article getArticleByPos(int pos){
        // CONTENT_POS_URI 就是 content 的 URI
        Uri uri = ContentUris.withAppendedid(Articles.CONTENT_POS_URI,pos);
        String[] projection=new String[]{
            Articles.ID,
            Articles.TITLE,
            Articles.ABSTRACT,
            Articles.URL
        };
        // DEFAULT_SORT_ORDER = "_id asc" 代表以 id 为 key，升序排列
        Cursor cursor = resolver.query(uri, projection, null,null,Articles.DEFAULT_SORT_ORDER);
        if(!cursor.moveToFirst()){
            return null;
        }
        intid=cursor.getInt(0);
        String title=cursor.getString(1);
        String abs = cursor.getString(2);
        String url = cursor.getString(3);

        return new Article(id,title,abs, ur1);
    }
}
```

## Step1: ContentResolver.query

```java
public final Cursor query(Uri uri, String[] projection,
        String selection, String[] selectionArgs, String sortOrder) {
    // 这个就是之前 获取 provider 的路径。
    IContentProvider provider = acquireProvider(uri);
    if (provider == null) {
        return null;
    }
    try {
        //...
        // 发起远程调用
        Cursor qCursor = provider.query(uri, projection, selection, selectionArgs, sortOrder);
        //...
        return new CursorWrapperInner(qCursor, provider);
    } catch (RemoteException e) {
        //...
    } catch(RuntimeException e) {
        //...
    }
}
```

## Step2: ContentProviderProxy.query

首先创建一个 CursorWindow 对象和一个 BulkCursorToCursorAdaptor。

```java
public Cursor query(Uri url, String[] projection, String selection,
        String[] selectionArgs, String sortOrder) throws RemoteException {
    //TODO make a pool of windows so we can reuse memory dealers
    CursorWindow window = new CursorWindow(false /* window will be used remotely */);
    BulkCursorToCursorAdaptor adaptor = new BulkCursorToCursorAdaptor();
    IBulkCursor bulkCursor = bulkQueryInternal(
        url, projection, selection, selectionArgs, sortOrder,
        adaptor.getObserver(), window,
        adaptor);
    if (bulkCursor == null) {
        return null;
    }
    return adaptor;
}
```

## Step3: new CursorWindow

CursorWindow 在创建的过程中，会创建一块共享内存，这块匿名共享内存会与 CursorWindow 对象 window 一起传递给 provider 组件。

Java 层中的每一个 CursorWindow 对象在 C++层中都有一个关联的 CursorWindow 对象。Java 层中的 CursorWindow 对象内部所使用的一块匿名共享内存就是通过 C++层中的 CursorWindow 对象来创建的，因此，在 Java 层中创建一个 CursorWindow 对象时，也需要在 C++层中创建一个 CursorWindow 对象，这是通过调用 CursorWindow 类的成员函数 native_init 来实现的。

```java
public class CursorWindow extends SQLiteClosable implements Parcelable {
    /** The pointer to the native window class */
    @SuppressWarnings("unused")
    private int nWindow;

    private int mStartPos;

    /**
     * Creates a new empty window.
     *
     * @param localWindow true if this window will be used in this process only
     */
    public CursorWindow(boolean localWindow) {
        mStartPos = 0;
        native_init(localWindow);
    }
    //..
    /** Does the native side initialization for an empty window */
    private native void native_init(boolean localOnly);
    //...
}
```

`native_init` 方法的内容如下。

```cpp
static void native_init_empty(JNIEnv * env, jobject object, jboolean localOnly)
{
    //...
    CursorWindow * window;
    // #define MAX_WINDOW_SIZE (1024 * 1024)
    window = new CursorWindow(MAX_WINDOW_SIZE);
    //...

    if (!window->initBuffer(localOnly)) {
        jniThrowException(env, "java/lang/IllegalStateException", "Couldn't init cursor window");
        delete window;
        return;
    }
    //...
    // 把 c++ 的 CursorWindow 地址值保存在 java 对象的成员 mWindow 上。
    SET_WINDOW(env, object, window);
}

// initBuffer 的实现
bool CursorWindow::initBuffer(bool localOnly)
{
    //...
    sp<MemoryHeapBase> heap;
    // 创建共享内存
    heap = new MemoryHeapBase(mMaxSize, 0, "CursorWindow");
    if (heap != NULL) {
        mMemory = new MemoryBase(heap, 0, mMaxSize);
        if (mMemory != NULL) {
            mData = (uint8_t *) mMemory->pointer();
            if (mData) {
                mHeader = (window_header_t *) mData;
                mSize = mMaxSize;
                // Put the window into a clean state
                clear();
            LOG_WINDOW("Created CursorWindow with new MemoryDealer: mFreeOffset = %d, mSize = %d, mMaxSize = %d, mData = %p", mFreeOffset, mSize, mMaxSize, mData);
                return true;                
            }
        } 
        LOGE("CursorWindow heap allocation failed");
        return false;
    } else {
        LOGE("failed to create the CursorWindow heap");
        return false;
    }
}
```

## Step4: ContentProviderProxy.bulkQueryInternal

将前面传进来的参数写入到 Parcel 对象 data 中，接着再通过 ContentProviderProxy 类内部的一个 Binder 代理对象 mRemote 向 ArticlesProvider 组件发送一个类型为 IContentProvider.QUERY_TRANSACTION 的进程间通信请求。

ArticlesProvider 组件处理完成这个类型为 IContentProvider.QUERY_TRANSACTION 的进程间通信请求之后，就会返回一个 CursorToBulkCursorAdaptor 代理对象 bulkCursor 给 MainActivity 组件，里面包含了 MainActivity 组件所请求的博客文章信息。最后将这个 CursorToBulkCursorAdaptor 代理对象保存在 BulkCursorToCursorAdaptor 对象 adaptor 中，以便 MainActivity 组件可以通过它来获得 ArticlesProvider 组件所返回的博客文章信息。

```java
    private IBulkCursor bulkQueryInternal(
        Uri url, String[] projection,
        String selection, String[] selectionArgs, String sortOrder,
        IContentObserver observer, CursorWindow window,
        BulkCursorToCursorAdaptor adaptor) throws RemoteException {
        Parcel data = Parcel.obtain();
        Parcel reply = Parcel.obtain();

        //... 
        // 写入共享内存信息
        window.writeToParcel(data, 0);
        // Flag for whether or not we want the number of rows in the
        // cursor and the position of the "_id" column index (or -1 if
        // non-existent).  Only to be returned if binder != null.
        // 标明是不是需要返回数据的元信息。
        final boolean wantsCursorMetadata = (adaptor != null);
        data.writeInt(wantsCursorMetadata ? 1 : 0);
        //...

        mRemote.transact(IContentProvider.QUERY_TRANSACTION, data, reply, 0);

        DatabaseUtils.readExceptionFromParcel(reply);

        IBulkCursor bulkCursor = null;
        // 获取返回的 CursorToBulkCursorAdaptor 对象的远程代理
        IBinder bulkCursorBinder = reply.readStrongBinder();
        if (bulkCursorBinder != null) {
            bulkCursor = BulkCursorNative.asInterface(bulkCursorBinder);

            if (wantsCursorMetadata) {
                int rowCount = reply.readInt();
                int idColumnPosition = reply.readInt();
                if (bulkCursor != null) {
                    // 保存这个代理到 BulkCursorToCursorAdaptor 中。
                    adaptor.set(bulkCursor, rowCount, idColumnPosition);
                }
            }
        }
        data.recycle();
        reply.recycle();

        return bulkCursor;
    }
```

## Step5: CursorWindow.writeToParcel

这一步我们分析，CursorWindow 是如何把匿名共享内存的信息写入到 Parcel 对象 data 中的。

```java
public void writeToParcel(Parcel dest, int flags) {
    dest.writeStrongBinder(native_getBinder());
    //...
}

private native IBinder native_getBinder();
```

这里使用 jni 方法获取一个 IBinder java 对象。

```cpp
static jobject native_getBinder(JNIEnv * env, jobject object)
{
    // 从 mWindow 成员转换成 window 对象
    CursorWindow * window = GET_WINDOW(env, object);
    if (window) {
        // 返回内部的 MemoryBase 对象，这个是一个 BBinder 对象。
        sp<IMemory> memory = window->getMemory();
        if (memory != NULL) {
            sp<IBinder> binder = memory->asBinder();
            // 将这个 binder 对象转换成 java 层 binder 对象。就是个 binderProxy（因为这个是一个 cpp 的 binder 本地对象。）
            return javaObjectForIBinder(env, binder);
        }
    }
    return NULL;
}
```

## Step6: ContentProviderNative.onTransact

`ContentProvider` 继承自 `ContentProviderNative`，在收到远程调用后，首先会触发 `onTransact` 方法。

```java
    public boolean onTransact(int code, Parcel data, Parcel reply, int flags)
            throws RemoteException {
        try {
            switch (code) {
                case QUERY_TRANSACTION:
                {
                    data.enforceInterface(IContentProvider.descriptor);

                    Uri url = Uri.CREATOR.createFromParcel(data);

                    //...
                    // 读取共享内存，并封装成一个 window 对象。
                    CursorWindow window = CursorWindow.CREATOR.createFromParcel(data);

                    // Flag for whether caller wants the number of
                    // rows in the cursor and the position of the
                    // "_id" column index (or -1 if non-existent)
                    // Only to be returned if binder != null.
                    // 读取是不是要返回元信息的标志位
                    boolean wantsCursorMetadata = data.readInt() != 0;
                    /*
                        调用 Transport 类的成员函数 bulkQuery 来获得一个 CursorToBulkCursorAdaptor 对象 bulkCursor。
                        这个 CursorToBulkCursorAdaptor 对象包含了 ArticlesProvider 组件返回给 MainActivity 组件的博客文章信息。接着将它写入到 Parcel 对象 reply 中，以便 ArticlesProvider 组件可以将它返回给 MainActivity 组件。
                    */
                    IBulkCursor bulkCursor = bulkQuery(url, projection, selection,
                            selectionArgs, sortOrder, observer, window);
                    reply.writeNoException();
                    if (bulkCursor != null) {
                        reply.writeStrongBinder(bulkCursor.asBinder());
                        // 如果需要获取元数据，那就从刚才的 bulkCursor 中进行元信息读取
                        if (wantsCursorMetadata) {
                            reply.writeInt(bulkCursor.count());
                            reply.writeInt(BulkCursorToCursorAdaptor.findRowIdColumnIndex(
                                bulkCursor.getColumnNames()));
                        }
                    } else {
                        reply.writeStrongBinder(null);
                    }

                    return true;
                }

                //...
            }
        } catch (Exception e) {
            DatabaseUtils.writeExceptionToParcel(reply, e);
            return true;
        }

        return super.onTransact(code, data, reply, flags);
    }
```

## Step7: CursorWindow.CREATOR.createFromParcel

这个函数就是用来从 binder 传递过来的数据中还原共享内存，并通过这个共享内存创建一个新的 CursorWindow。这个 nativeBinder 在前面的分析来看就是一个 BinderProxy。

```java
public static final Parcelable.Creator<CursorWindow> CREATOR
        = new Parcelable.Creator<CursorWindow>() {
    public CursorWindow createFromParcel(Parcel source) {
        return new CursorWindow(source);
    }

    public CursorWindow[] newArray(int size) {
        return new CursorWindow[size];
    }
};

private CursorWindow(Parcel source) {
    IBinder nativeBinder = source.readStrongBinder();
    mStartPos = source.readInt();

    native_init(nativeBinder);
}

private native void native_init(IBinder nativeBinder);
```

## Step8: CursorWindow.native_init

```cpp
static void native_init_memory(JNIEnv * env, jobject object, jobject memObj)
{   
    // 将这个 java BinderProxy 对象中解析出来 c++ 的 binder 对象，其实就是一个 binder 代理对象。
    sp<IMemory> memory = interface_cast<IMemory>(ibinderForJavaObject(env, memObj));
    if (memory == NULL) {
        jniThrowException(env, "java/lang/IllegalStateException", "Couldn't get native binder");
        return;
    }

    CursorWindow * window = new CursorWindow();
    if (!window) {
        jniThrowException(env, "java/lang/RuntimeException", "No memory for native window object");
        return;
    }
    if (!window->setMemory(memory)) {
        jniThrowException(env, "java/lang/RuntimeException", "No memory in memObj");
        delete window;
        return;
    }

    //...
    SET_WINDOW(env, object, window);
}

bool CursorWindow::setMemory(const sp<IMemory>& memory)
{
    mMemory = memory;
    // 保存地址 和 尺寸
    mData = (uint8_t *) memory->pointer();
    //...
    ssize_t size = memory->size();
    mSize = size;
    mMaxSize = size;
    mFreeOffset = size;
    //...
    return true;
}
```

## Step9: Transport.bulkQuery

Transport 类是 ContentProvider 的内部类，这里首先调用 ContentProvider 的 query 方法(也就是我们自己定义的 ContentProvider 中重写的 query 方法)来获取对应信息，这些信息保存在 Cursor 对象中。

```java
public IBulkCursor bulkQuery(Uri uri, String[] projection,
        String selection, String[] selectionArgs, String sortOrder,
        IContentObserver observer, CursorWindow window) {
    //...
    Cursor cursor = ContentProvider.this.query(uri, projection,
            selection, selectionArgs, sortOrder);
    //...
    return new CursorToBulkCursorAdaptor(cursor, observer,
            ContentProvider.this.getClass().getName(),
            hasWritePermission(uri), window);
}
```

## Step10: new CursorToBulkCursorAdaptor

参数 cursor 指向了一个 SQLiteCursor 对象，它实现了 CrossProcessCursor 接口，并且继承了 AbstractWindowedCursor 类，因此，第 9 行的 if 语句为 true。首先将参数 cursor 转换成一个 AbstractWindowedCursor 对象，然后再调用它的成员函数 setWindow 将参数 window 所描述的一个 CursorWindow 对象保存在它里面。

```java
public CursorToBulkCursorAdaptor(Cursor cursor, IContentObserver observer, String providerName,
        boolean allowWrite, CursorWindow window) {
    try {
        mCursor = (CrossProcessCursor) cursor;
        if (mCursor instanceof AbstractWindowedCursor) {
            AbstractWindowedCursor windowedCursor = (AbstractWindowedCursor) cursor;
            //...
            // 保存 window
            windowedCursor.setWindow(window);
        } else {
            //...
        }
    } catch (ClassCastException e) {
        //...
    }
    //...
}
```

## Step11: CursorToBulkCursorAdaptor.count

然后返回第六步，我们需要用这个 Adaptor 先获取一下元数据。这里 mCursor 就是刚才构造时传入的 SQLiteCursor。

```java
    public int count() {
        return mCursor.getCount();
    }
```

## Step12: SQLiteCursor.getCount

SQLiteCursor 类的成员变量 mCount 的初始值为 NO_COUNT，表示包含在 SQLiteCursor 类中的数据库查询计划还没有被执行。当这个数据库查询计划被执行之后，SQLiteCursor 类的成员变量 mCount 就用来保存从数据库中获得的数据的总行数。

```java
    public int getCount() {
        if (mCount == NO_COUNT) {
            fillWindow(0);
        }
        return mCount;
    }
```

## Step13: SQLiteCursor.fillWindow

SQLiteCursor 类的成员变量 mWindow 是从父类 AbstractWindowedCursor 继承下来的，它里面引用了一块匿名共享内存。当 SQLiteCursor 类的成员变量 mQuery 所描述的数据库查询计划执行完成之后，从数据库中获得的数据，即 MainActivity 组件所请求的博客文章条目就会保存在这块匿名共享内存中。

```java
    private void fillWindow (int startPos) {
        //...
        mWindow.setStartPosition(startPos);
        mCount = mQuery.fillWindow(mWindow, mInitialRead, 0);
        //...
    }
```

## Step14: SQLiteQuery.fillWindow

调用了 SQLiteQuery 类的成员函数 native_fill_window 来执行在前面的中所创建的一个数据库查询计划，执行结果就保存在参数 window 所描述的一个 CursorWindow 对象的内部所引用的一块匿名共享内存中。

```java
    /* package */ int fillWindow(CursorWindow window,
            int maxRead, int lastPos) {
        //...
        try {
            //...
            try {
                //...
                // if the start pos is not equal to 0, then most likely window is
                // too small for the data set, loading by another thread
                // is not safe in this situation. the native code will ignore maxRead
                int numRows = native_fill_window(window, window.getStartPosition(), mOffsetIndex,
                        maxRead, lastPos);

                // Logging
                //...
                return numRows;
            } catch (IllegalStateException e){
                //...
            } catch (SQLiteDatabaseCorruptException e) {
                //...
            } finally {
                //...
            }
        } finally {
            //...
        }
    }
```


