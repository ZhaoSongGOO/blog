# Binder

## 简介

Binder进程间通信机制是在OpenBinder的基础上实现的[插图]，它采用CS通信方式，其中，提供服务的进程称为Server进程，而访问服务的进程称为Client进程。同一个Server进程可以同时运行多个组件来向Client进程提供服务，这些组件称为Service组件[插图]。同时，同一个Client进程也可以同时向多个Service组件请求服务，每一个请求都对应有一个Client组件，或者称为Service代理对象。Binder进程间通信机制的每一个Server进程和Client进程都维护一个Binder线程池来处理进程间的通信请求，因此，Server进程和Client进程可以并发地提供和访问服务。

Server进程和Client进程的通信要依靠运行在内核空间的Binder驱动程序来进行。Binder驱动程序向用户空间暴露了一个设备文件/dev/binder，使得应用程序进程可以间接地通过它来建立通信通道。Service组件在启动时，会将自己注册到一个Service Manager组件中，以便Client组件可以通过ServiceManager组件找到它。因此，我们将Service Manager组件称为Binder进程间通信机制的上下文管理者，同时由于它也需要与普通的Server进程和Client进程通信，我们也将它看作是一个Service组件，只不过它是一个特殊的Service组件。

<img src="android/framework/binder/resources/1.png" style="width:80%">

从图可以看出，Client、Service和Service Manager运行在用户空间，而Binder驱动程序运行在内核空间，其中，Service Manager和Binder驱动程序由系统负责提供，而Client和Service组件由应用程序来实现。Client、Service和Service Manager均是通过系统调用open、mmap和ioctl来访问设备文件/dev/binder，从而实现与Binder驱动程序的交互，而交互的目的就是为了能够间接地执行进程间通信。

## 基础数据结构

### binder_work

描述一个待处理的工作项, 其中 entry 是一个双向链表的结构，用来将 binder_work 组织起来成一个链表。type 表示工作项的类型。

```c

struct list_head {
	struct list_head *next, *prev;
};

struct binder_work {
	struct list_head entry;
	enum {
		BINDER_WORK_TRANSACTION = 1, // 有新的 binder 事务（RPC 调用）需要处理。
		BINDER_WORK_TRANSACTION_COMPLETE, // 事务处理完成，需要通知对方。
		BINDER_WORK_NODE, // 节点相关的管理操作（比如引用计数）。
		BINDER_WORK_DEAD_BINDER, // binder 对象死亡，需要通知注册了死亡回调的进程。
		BINDER_WORK_DEAD_BINDER_AND_CLEAR, // 对象死亡并且需要清理相关资源。
		BINDER_WORK_CLEAR_DEATH_NOTIFICATION, // 需要清除死亡通知。
	} type;
};
```

这里我有两个疑问，第一这个 list_head 结构是如何实现双向链表的，第二既然这个 binder_work 可以代表这么多情况，但是看起来内容很简单，如何承载更多的信息呢？

先回答第一个问题，list_head 是 linux 内核中使用非常普遍的双向链表管理结构，在使用的过程中牵扯到一个宏 container_of.

我们先举个例子：

```c
// 初始化链表头
struct list_head list;
// INIT_LIST_HEAD(&list);
list.next = &list;
list.prec = &list;

struct binder_work work{.type=BINDER_WORK_TRANSACTION};

list_add(&work->entry, &list);

// 遍历

struct binder_work *node;
list_for_each_entry(node, &list, entry){
	printk("type=%d", node->type);
}

```

首先我们初始化一个链表头，这个头的 next 和 prev 都指向自己。随后我们构造自己的 binder_node, 并通过 list_add 来将 binder_node 添加到链表中，其实只是将 binder_node 的 entry 添加到链表中。list_add 实现如下,就是个简单的双向链表头插法。

```c
static inline void __list_add(struct list_head *new,
			      struct list_head *prev,
			      struct list_head *next)
{
	next->prev = new;
	new->next = next;
	new->prev = prev;
	prev->next = new;
}

static inline void list_add(struct list_head *new, struct list_head *head)
{
	__list_add(new, head, head->next);
}
```

随后我们可能会在需要的时候进行遍历，在遍历的过程中，声明一个目标类型的指针，用来承载迭代过程中的目标对象，然后这个 list_for_each_entry 使用起来很神奇，第一个参数是我们刚声明的指针，第二个参数是链表地址，第三个参数是list_head 在你的结构里面的字段名，例如对于 binder_node 来说，就是 entry。可以看到这个宏展开后就是个 for(x;y;z) 的结构。

- 使用 list_entry 来获取 entry 只想的 biner_work 节点，并返回地址到 pos。
- prefetch 不需要关注，这个是一个优化，即将内容优先加载到 L1 缓存中。
- pos->next 进入下一个节点。

这里最有意思的就是这个 list_entry, 可以看到他接受的是 list_head 指针、binder_work 类型参数、list_head 指针在 binder_work 结构中对应的结构名 entry.

随后 list_entry 直接转调 container_of 宏，这个宏只做了:

<img src="android/framework/binder/resources/2.png" style="width:20%">

- 将 list_head 地址类型关联到 binder_work->entry。方便后续进行指针计算。
- 使用 offset 获取 entry 字段在 binder_work 中的地址偏移。随后使用 list_head 指针减去 这个偏移量就是 binder_work 的地址。

更有意思的是为了获取 offset，是先将地址 0 转换成 binder_work 指针类型，随后获取成员地址，那这样这个成员的地址其实就是偏移。需要注意的是，这里是获取成员地址操作，这是一个编译期逻辑，而不是空指针访问数据，空指针访问会触发段错误。


```c
// linux/stddef.h
#define offsetof(TYPE, MEMBER) ((size_t) &((TYPE *)0)->MEMBER)

// linux/kernel.h
#define container_of(ptr, type, member) ({			\
	const typeof( ((type *)0)->member ) *ç = (ptr);	\
	(type *)( (char *)__mptr - offsetof(type,member) );})

// linux/list.h
#define list_entry(ptr, type, member) \
	container_of(ptr, type, member)

/**
 * list_for_each_entry	-	iterate over list of given type
 * @pos:	the type * to use as a loop cursor.
 * @head:	the head for your list.
 * @member:	the name of the list_struct within the struct.
 */
#define list_for_each_entry(pos, head, member)				\
	for (pos = list_entry((head)->next, typeof(*pos), member);	\
	     prefetch(pos->member.next), &pos->member != (head); 	\
	     pos = list_entry(pos->member.next, typeof(*pos), member))
```