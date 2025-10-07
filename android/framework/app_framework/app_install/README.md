# Android 应用安装与显示

Android 系统在启动过程中，会扫描系统中的特定目录，以便可以对保存在里面的应用程序进行安装。这是通过 Package 管理服务 PackageManagerService 来实现的。

Package 管理服务 PackageManagerService 在安装一个应用程序的过程中，主是完成两件事情。

1. 第一件事情是解析这个应用程序的配置文件 AndroidManifest.xml，以便可以获得它的安装信息；
2. 第二件事情是为这个应用程序分配 Linux 用户 ID 和 Linux 用户组 ID，以便它可以在系统中获得合适的运行权限。

Android 系统启动过程的最后一步是启动一个 Home 应用程序，用来显示系统中已经安装了的应用程序。Android 系统提供了一个默认的 Home 应用程序——Launcher。应用程序 Launcher 在启动过程中，首先会请求 Package 管理服务 PackageManagerService 返回系统中已经安装了的应用程序的信息，接着再分别将这些应用程序信息封装成一个快捷图标显示在系统的屏幕中，以便用户可以通过点击这些快捷图标来启动相应的应用程序。

## [App 安装过程](android/framework/app_framework/app_install/install_app_process.md)

## [应用程序显示过程](android/framework/app_framework/app_install/launcher_app.md)



