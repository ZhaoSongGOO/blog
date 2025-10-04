# ContentProvider 数据共享原理

Content Provider 组件通过 Binder 进程间通信机制来突破以应用程序为边界的权限控制，同时，它又以匿名共享内存作为数据传输媒介，从而提供了一种高效的数据共享方式。

Content Provider 通信过程中，client 组件向 provider 请求数据的时候，provider 需要将数据封装在一个 SQLite 游标 (Cursor) 中，返回给 client 组件。

这里我们先看下 Cursor 的类层次。

<img src="android/framework/app_framework/content_provider/resources/1.png" style="width:100%">

client 组件在请求 provider 组件返回其内部的博客文章信息之前，首先会在当前应用程序进程中创建一个 CursorWindow 对象。CursorWindow 类实现了 Parcelable 接口，并且在内部包含了一块匿名共享内存。接下来 client 组件就会通过 Binder 进程间通信机制将前面所创建的 CursorWindow 对象（连同它内部的匿名共享内存）传递给 provider 组件。

provider 组件获得了 client 组件发送过来的 CursorWindow 对象之后，就会创建一个 SQLiteCursor 对象。SQLiteCursor 类继承了 AbstractWindowedCursor 类，而 AbstractWindowedCursor 类又继承了 AbstractCursor 类。AbstractCursor 类实现了 CrossProcessCursor 接口，而 CrossProcessCursor 接口又是从 Cursor 接口继承下来的。因此，SQLiteCursor 类可以用来描述一个游标，即可以用来传输 Content Provider 组件中的共享数据。

AbstractWindowedCursor 类有一个类型为 CursorWindow 的成员变量 mWindow。provider 组件在创建 SQLiteCursor 对象时，会调用它的成员函数 setWindow 将 client 组件发送过来的 CursorWindow 对象保存在其父类 AbstractWindowedCursor 的成员变量 mWindow 中。

SQLiteCursor 对象创建完成之后，provider 组件就会将 client 组件所请求的博客文章信息保存在这个 SQLiteCursor 对象中，实际上是保存在与它所关联的一个 CursorWindow 对象的内部的一块匿名共享内存中。由于 client 组件是可以访问这块匿名共享内存的，因此，它就可以通过这块匿名共享内存来获得 provider 组件返回给它的博客文章信息。

由于 SQLiteCursor 对象并不是一个 Binder 本地对象，因此，provider 组件不能直接将它返回给 client 组件使用。provider 组件首先会创建一个 CursorToBulkCursorAdaptor 对象，用来适配前面所创建的一个 SQLiteCursor 对象，即将这个 SQLiteCursor 对象保存在它的成员变量 mCursor 中。CursorToBulkCursorAdaptor 类继承了 BulkCursorNative 类，而 BulkCursorNative 类实现了 IBulkCursor 接口，并且继承了 IBinder 类，因此，它可以用来描述一个实现了 IBulkCursor 接口的 Binder 本地对象。provider 组件接着就会将这个 CursorToBulkCursorAdaptor 对象返回给 client 组件。

client 组件在请求 provider 组件返回其内部的博客文章信息之前，除了会创建一个 CursorWindow 对象之外，还会创建一个 BulkCursorToCursorAdaptor 对象，并且前面所创建的 CursorWindow 对象就是保存在它的父类 AbstractWindowedCursor 的成员变量 mWindow 中的。

client 组件接收到 provider 组件返回来的 CursorToBulkCursorAdaptor 对象之后，实际上获得的是一个 CursorToBulkCursorAdaptor 代理对象，接着就会将它保存在之前所创建的一个 BulkCursorToCursorAdaptor 对象的成员变量 mBulkCursor 中。这时候 client 组件就可以通过这个 BulkCursorToCursorAdaptor 对象来读取 provider 组件返回来的博客文章信息了。

依据这些类，我们总结出下面的 Content Provider 数据共享模型。

<div style="width:100%;text-align:center">
    <img src="android/framework/app_framework/content_provider/resources/2.png" style="width:50%">
</div>

1. 左边的 BulkCursorToCursorAdaptor 对象的成员变量 mBulkCursor 引用了右边的 CursorToBulkCursorAdaptor 对象。
2. 左边的 CursorWindow 对象和右边的 CursorWindow 对象引用了同一块匿名共享内存。


这时候系统只是在 client 组件和 provider 组件之间建立了一个数据共享模型，provider 组件还没有真正把 client 组件所请求的博客文章信息写入到它们所共享的一块匿名共享内存中，即右边的 SQLiteCursor 对象还没有将 client 组件所请求的博客文章信息从数据库中读取出来。

当 client 组件第一次通过左边的 BulkCursorToCursorAdaptor 对象来读取 provider 组件返回来的博客文章信息时，左边的 BulkCursorToCursorAdaptor 对象就会首先通过其成员变量 mBulkCursor 来请求右边的 CursorToBulkCursorAdaptor 对象将它所请求的博客文章信息写入到右边的 CursorWindow 对象所引用的一块匿名共享内存中。

右边的 CursorToBulkCursorAdaptor 对象实际上是通过其内部的 SQLiteCursor 对象来获得 client 组件所请求的博客文章信息的，而这个 SQLiteCursor 对象又是通过调用其内部的数据库查询计划 mQuery 的成员函数 fillWindow 来从数据库 mDatabase 中获得 client 组件所请求的博客文章信息的。

如果 client 组件在请求 provider 组件返回其内部的博客文章信息时，要求 provider 组件返回符合条件的博客文章信息的元数据，例如，要求返回符合条件的博客文章信息的行数，即符合条件的博客文章的数量，那么 provider 组件在将右边的 CursorToBulkCursorAdaptor 对象返回给 client 组件之前，就会通过右边的 SQLiteCursor 对象从数据库 mDatabase 中获得 client 组件所请求的博客文章信息，并且保存在右边的 CursorWindow 对象所引用的一块匿名共享内存中。因为只有获得了这些博客文章信息之后，provider 组件才能将它的元数据返回给 client 组件。