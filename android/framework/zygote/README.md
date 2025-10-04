# Zygote 和 System 进程启动

在 Android 系统中，所有的应用程序进程，以及用来运行系统关键服务的 System 进程都是由 Zygote 进程负责创建的，因此，我们将它称为进程孵化器。

Zygote 进程是通过复制自身的方式来创建 System 进程和应用程序进程的。由于 Zygote 进程在启动时会在内部创建一个虚拟机实例，因此，通过复制 Zygote 进程而得到的 System 进程和应用程序进程可以快速地在内部获得一个虚拟机实例拷贝。

Zygote 进程在启动完成之后，会马上将 System 进程启动起来，以便它可以将系统的关键服务启动起来。这些关键服务包括 ActivityManagerService 和 Content 管理服务 ContentService，以及 Window 管理服务 WindowManagerService 和 Package 管理服务 PackageManagerService。

## [Zygote 进程启动](android/framework/zygote/zygote_launch.md)