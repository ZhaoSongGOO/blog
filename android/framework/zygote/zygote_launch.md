# Zygote 进程启动脚本以及启动流程

## Zygote 进程启动脚本

Zygote 进程是由 Android 系统的第一个进程 init 启动起来的。init 进程是在内核加载完成之后就启动起来的，它在启动的过程中，会读取根目录下的一个脚本文件 init.rc，以便可以将其他需要开机启动的进程也一起启动起来。

```cpp
/*
第 1 行表示 Zygote 进程是以服务的形式启动的，并且它所对应的应用程序文件为/system/bin/app_process。
接下来的四个选项是 Zygote 进程的启动参数，其中，最后一个参数"--start-system-server"表示 Zygote 进程在启动完成之后，需要马上将 System 进程也启动起来。
*/
service zygote /system/bin/app_process -Xzygote /system/bin --zygote --start-system-server
    /* 
    第 2 行表示 Zygote 进程在启动的过程中，需要在内部创建一个名称为"zygote"的 Socket。
    这个 Socket 是用来执行进程间通信的，它的访问权限被设置为 666，即所有用户都可以对它进行读和写。
    */
    socket zygote stream 666
```

init 进程的逻辑在 init.c 中，因为 zygote 被配置成 service 启动，这会触发其 service_start 方法来创建任务。

参数 svc 指向了一个 service 结构体，它的成员变量 sockets 和 args 分别保存了即将要启动的服务的 Socket 列表和静态启动参数列表。

```c
void service_start(struct service *svc, const char *dynamic_args)
{
    //...
    pid_t pid;
    //...

    pid = fork(); // fork 一个新进程，返回 0 意味着子进程。

    if (pid == 0) {
        struct socketinfo *si;
        //...
        // 遍历 socket 列表
        for (si = svc->sockets; si; si = si->next) {
            int socket_type = (
                    !strcmp(si->type, "stream") ? SOCK_STREAM :
                        (!strcmp(si->type, "dgram") ? SOCK_DGRAM : SOCK_SEQPACKET));
            // 创建 socket，返回的是文件描述符
            int s = create_socket(si->name, socket_type,
                                  si->perm, si->uid, si->gid);
            if (s >= 0) {
                // 发布 socket
                publish_socket(si->name, s);
            }
        }
        //...
        // 这里使用 execve 方法来启动 `/system/bin/app_process` 方法，并传入参数
        if (!dynamic_args) {
            if (execve(svc->args[0], (char**) svc->args, (char**) ENV) < 0) {
                ERROR("cannot execve('%s'): %s\n", svc->args[0], strerror(errno));
            }
        } else {
            char *arg_ptrs[INIT_PARSER_MAXARGS+1];
            int arg_idx = svc->nargs;
            char *tmp = strdup(dynamic_args);
            char *next = tmp;
            char *bword;

            /* Copy the static arguments */
            memcpy(arg_ptrs, svc->args, (svc->nargs * sizeof(char *)));

            while((bword = strsep(&next, " "))) {
                arg_ptrs[arg_idx++] = bword;
                if (arg_idx == INIT_PARSER_MAXARGS)
                    break;
            }
            arg_ptrs[arg_idx] = '\0';
            // Env 传递
            execve(svc->args[0], (char**) arg_ptrs, (char**) ENV);
        }
        _exit(127);
    }

    //...
}
```

下面我们分析一下 `create_socket` 和 `publish_socket` 两个方法的实现。

`create_socket` 就是创建一个 socket 套接字，并与文件 `/dev/socket/zygote` 绑定。

```c
int create_socket(const char *name, int type, mode_t perm, uid_t uid, gid_t gid)
{
    struct sockaddr_un addr;
    int fd, ret;

    fd = socket(PF_UNIX, type, 0);
    //...

    memset(&addr, 0 , sizeof(addr));
    addr.sun_family = AF_UNIX;
    // #define ANDROID_SOCKET_DIR		"/dev/socket"
    snprintf(addr.sun_path, sizeof(addr.sun_path), ANDROID_SOCKET_DIR"/%s",
             name);
    //...

    ret = bind(fd, (struct sockaddr *) &addr, sizeof (addr));
    //...

    chown(addr.sun_path, uid, gid);
    chmod(addr.sun_path, perm);

    //...

    return fd;
    //...
}
```

`publish_socket` 实现如下，首先将宏 ANDROID_SOCKET_ENV_PREFIX 和参数 name 所描述的两个字符串连接在一起，保存在字符串 key 中。宏 ANDROID_SOCKET_ENV_PREFIX 的值为"ANDROID_SOCKET_"​，而参数 name 的值为"zygote"​，因此，前面得到的字符串 key 的值就为"ANDROID_SOCKET_zygote"​。

```c
static void publish_socket(const char *name, int fd)
{
    // #define ANDROID_SOCKET_ENV_PREFIX	"ANDROID_SOCKET_"
    char key[64] = ANDROID_SOCKET_ENV_PREFIX;
    char val[64];

    strlcpy(key + sizeof(ANDROID_SOCKET_ENV_PREFIX) - 1,
            name,
            sizeof(key) - sizeof(ANDROID_SOCKET_ENV_PREFIX));
    snprintf(val, sizeof(val), "%d", fd);
    // 将这个 fd 设置为全局变量 ANDROID_SOCKET_zygote 的值，这个变量会被 fork 后的 exec 的时候传入。
    add_environment(key, val);

    /* make sure we don't close-on-exec */
    // 这行代码的作用是清除指定文件描述符 `fd` 上的 `FD_CLOEXEC` 标志。这样做的直接效果是，确保这个文件描述符 `fd` 在当前进程通过 `exec()` 系统调用启动一个新程序后，不会被自动关闭，而是会被这个新程序继承过去。
    fcntl(fd, F_SETFD, 0);
}
```

## Zygote 进程启动流程