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

更有意思的是为了获取 offset，是先将地址 0 转换成 binder_work 指针类型，随后获取成员地址，那这样这个成员的地址其实就是偏移。需要注意的是，这里是获取成员地址操作，这是一个编译期逻辑，而不是空指针访问数据，空指针访问会触发段错误。如何区分是获取成员地址还是空指针访问，我理解区别就在于有没有声明对应的类型指针，声明了就是空指针访问，否则就是获取地址操作。


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
然后是第二个问题，这么简单的一个结构体是如何承载不同 binder 工作项的信息的。

其实这个 binder_work 只是一个"基类" 或者说标识，它用来在真正的 binder_work_xxx 中只是一个成员。

例如 binder_transaction 这个子类。

```c
struct binder_transaction {
    struct binder_work work;   // 头部，嵌入了 binder_work
    // 下面是事务的详细内容
    struct binder_process *from;
    struct binder_thread *from_thread;
    struct binder_transaction *to_parent;
    struct binder_transaction *to_child;
    struct binder_node *to_node;
    struct binder_buffer *buffer;
    unsigned int code;
    unsigned int flags;
    // ... 还有很多其他事务相关字段
};
```

### binder_node

代表一个 server 组件的实体对象，每当一个进程（比如 SystemServer）把某个 Binder 服务注册到 Binder 驱动时，驱动就会为这个服务分配一个 `binder_node` 结构体,就像 SystemService 进程一样，一个进程可能提供了多个服务，每一个服务都对应着一个 binder_node。

```c
struct binder_node {
	int debug_id;
	struct binder_work work;
	union {
		struct rb_node rb_node;
		struct hlist_node dead_node;
	};
	struct binder_proc *proc;
	struct hlist_head refs;
	int internal_strong_refs;
	int local_weak_refs;
	int local_strong_refs;
	void __user *ptr;
	void __user *cookie;
	unsigned has_strong_ref : 1;
	unsigned pending_strong_ref : 1;
	unsigned has_weak_ref : 1;
	unsigned pending_weak_ref : 1;
	unsigned has_async_transaction : 1;
	unsigned accept_fds : 1;
	int min_priority : 8;
	struct list_head async_todo;
};
```
1. **rb_node**
每个进程（`binder_proc`）可能会注册/持有多个 Binder 实体对象（比如一个进程可以有多个 Binder 服务）。为了高效管理这些对象，Binder 驱动在每个 `binder_proc` 里，用**红黑树（rbtree）**来存储和查找它所拥有的所有 `binder_node`，每个 binder_node 以 rb_node 的形式称为红黑树的节点。至于如何通过 rb_node 定位到 binder_node 呢？ 那就还是之前提到的 container_of 宏。

2. **proc**

proc 成员是一个 binder_proc 类型，指向的是提供该 binder_node 的进程实体，也就是说，`node->proc` 让你知道“这个 Binder 服务是哪个进程拥有的”。

3. **refs**

一个Binder实体对象可能会同时被多个Client组件引用，因此，Binder驱动程序就使用结构体binder_ref来描述这些引用关系，并且将引用了同一个Binder实体对象的所有引用都保存在一个hash列表中。这个hash列表通过Binder实体对象的成员变量refs来描述，而Binder驱动程序通过这个成员变量就可以知道有哪些Client组件引用了同一个Binder实体对象。

4. **local_strong_refs, internal_strong_refs, local_weak_refs**

这三个成员从名字可以看出用来记录不同来源对于该 binder_node 的引用状态，从而控制其生命周期。

- internal_strong_refs:统计Binder 驱动内部（比如 binder_ref 结构体）对该 binder_node 的强引用数量。主要来自于其他进程通过 handle 强引用该 Binder 服务对象时，Binder 驱动会增加 internal_strong_refs。

- local_strong_refs: 统计宿主进程内部对该 binder_node 的强引用数量。当宿主进程内部有 Java 层强引用（比如 ServiceManager 持有某个 Service 的 IBinder 对象），会增加 local_strong_refs。

- local_weak_refs: 统计宿主进程内部对该 binder_node 的弱引用数量。弱引用不会阻止对象被销毁，只是用来判断“有没有人在关注这个对象”。

5. **ptr, cookie**

ptr 和 cookie 指向两个用户空间的地址，其中，成员变量cookie指向该Service组件的地址，而成员变量ptr指向该Service组件内部的一个引用计数对象（类型为weakref_impl）的地址。

6. **has_async_transaction**

这个字段来表明当前 binder_node 即 server 组件是不是正在处理异步事务。一般情况下，Binder驱动程序都是将一个事务保存在一个线程的一个todo队列中的，表示要由该线程来处理该事务。每一个事务都关联着一个Binder实体对象，表示该事务的目标处理对象，即要求与该Binder实体对象对应的Service组件在指定的线程中处理该事务。然而，当Binder驱动程序发现一个事务是异步事务时，就会将它保存在目标Binder实体对象的一个异步事务队列中，这个异步事务队列就是由该目标Binder实体对象的成员变量async_todo来描述的。异步事务的定义是那些单向的进程间通信请求，即不需要等待应答的进程间通信请求，与此相对的便是同步事务。因为不需要等待应答，Binder驱动程序就认为异步事务的优先级低于同步事务，具体就表现为在同一时刻，一个Binder实体对象的所有异步事务至多只有一个会得到处理，其余的都等待在异步事务队列中，而同步事务就没有这个限制。

7. **work**

binder_node 中有一个 binder_work 成员 work，就如刚才说的，binder_work 代表一个事务，那 node 为什么要持有 work 呢？主要目的是进行生命周期同步，当一个Binder实体对象的引用计数由0变成1，或者由1变成0时，Binder驱动程序就会请求相应的Service组件增加或者减少其引用计数。这时候Binder驱动程序就会将该引用计数修改操作封装成一个类型为binder_node的工作项，即将一个Binder实体对象的成员变量work的值设置为BINDER_WORK_NODE，并且将它添加到相应进程的todo队列中去等待处理。

8. **min_priority**

用来描述 binder 服务执行服务逻辑所在线程的线程优先级。

9. **accept_fds**

accept_fds 用于标记该 Binder 服务对象是否允许接收文件描述符。- 在 Binder 跨进程通信过程中，除了普通的数据，还可以通过 Binder 机制传递文件描述符（比如 socket、文件、管道等）。但有些 Binder 服务出于安全或设计考虑，不希望/不允许接收 FD，以防止资源泄漏或被攻击。 这时，`accept_fds` 就作为一个开关来控制：

- 1/true：允许通过 Binder 传递 FD 给该服务对象。
- 0/false：不允许通过 Binder 传递 FD，驱动会拒绝或丢弃这类请求。

### binder_ref_death

```c
struct binder_ref_death {
	struct binder_work work;
	void __user *cookie;
};
```

结构体binder_ref_death用来描述一个Service组件的死亡接收通知。在正常情况下，一个Service组件被其他Client进程引用时，它是不可以销毁的。然而，Client进程是无法控制它所引用的Service组件的生命周期的，因为Service组件所在的进程可能会意外地崩溃，从而导致它意外地死亡。一个折中的处理办法是，Client进程能够在它所引用的Service组件死亡时获得通知，以便可以做出相应的处理。这时候Client进程就需要将一个用来接收死亡通知的对象的地址注册到Binder驱动程序中。

成员变量cookie用来保存负责接收死亡通知的对象的地址，成员变量work的取值为BINDER_WORK_DEAD_BINDER、BINDER_WORK_CLEAR_DEATH_NOTIFICATION或者BINDER_WORK_DEAD_BINDER_AND_CLEAR，用来标志一个具体的死亡通知类型。

Binder驱动程序决定要向一个Client进程发送一个Service组件死亡通知时，会将一个binder_ref_death结构体封装成一个工作项，并且根据实际情况来设置该结构体的成员变量work的值，最后将这个工作项添加到Client进程的todo队列中去等待处理。

什么时候会发送死亡通知呢?

client 在注册了死亡监听后，binder 驱动会在下面两种场景发送死亡通知。

- 当Binder驱动程序监测到一个Service组件死亡时，它就会找到该Service组件对应的Binder实体对象，然后通过Binder实体对象的成员变量refs就可以找到所有引用了它的Client进程，最后就找到这些Client进程所注册的死亡接收通知，即一个binder_ref_death结构体。这时候Binder驱动程序就会将该binder_ref_death结构体添加到Client进程的todo队列中去等待处理。在这种情况下，Binder驱动程序将死亡通知的类型设置为BINDER_WORK_DEAD_BINDER。

- 当Client进程向Binder驱动程序注册一个死亡接收通知时，如果它所引用的Service组件已经死亡，那么Binder驱动程序就会马上发送一个死亡通知给该Client进程。在这种情况下，Binder驱动程序也会将死亡通知的类型设置为BINDER_WORK_DEAD_BINDER。


client 也可以注销一个死亡监听，在注销的时候，binder 驱动也会发送一个类型为 binder_ref_death 的工作项到 client 进程的 todo 队列中。

- 如果Client进程在注销一个死亡接收通知时，相应的Service组件还没有死亡，那么Binder驱动程序就会找到之前所注册的一个binder_ref_death结构体，并且将它的类型work修改为BINDER_WORK_CLEAR_DEATH_NOTIFICATION，然后再将该binder_ref_death结构体封装成一个工作项添加到该Client进程的todo队列中去等待处理。

- 如果Client进程在注销一个死亡接收通知时，相应的Service组件已经死亡，那么Binder驱动程序就会找到之前所注册的一个binder_ref_death结构体，并且将它的类型work修改为BINDER_WORK_DEAD_BINDER_AND_CLEAR，然后再将该binder_ref_death结构体封装成一个工作项添加到该Client进程的todo队列中去等待处理。

### binder_ref

binder_ref 代表一个进程对另一个进程 Binder 实体对象 (binder_node) 的引用。在 Binder 体系中，每个进程只能通过 handle（整数句柄）来引用别的进程的 Binder 服务对象，而不能直接访问 binder_node。handle 和 binder_node 的映射关系，就是由 `binder_ref` 结构体来维护的。

```c
struct binder_ref {
	/* Lookups needed: */
	/*   node + proc => ref (transaction) */
	/*   desc + proc => ref (transaction, inc/dec ref) */
	/*   node => refs + procs (proc exit) */
	int debug_id;
	struct rb_node rb_node_desc;
	struct rb_node rb_node_node;
	struct hlist_node node_entry; // binder_node 会有一个 hlist_head refs 成员保存所有引用了他的 binder_ref, 这个node_entry 就是对应的节点。
	struct binder_proc *proc;  // 拥有这个引用的进程，一般来说是 client 所在的进程。
	struct binder_node *node; // 引用的实体对象 binder_node
	uint32_t desc;  // 句柄值或者称为描述符，它是用来描述一个Binder引用对象的。在Client进程的用户空间中，一个Binder引用对象是使用一个句柄值来描述的，因此，当Client进程的用户空间通过Binder驱动程序来访问一个Service组件时，它只需要指定一个句柄值，Binder驱动程序就可以通过该句柄值找到对应的Binder引用对象，然后再根据该Binder引用对象的成员变量node找到对应的Binder实体对象，最后就可以通过该Binder实体对象找到要访问的Service组件。
	int strong;
	int weak;
	struct binder_ref_death *death;
};
```

desc 在一个进程范围内是唯一的，也就是说在不同的进程下，同一个 desc 可能代表不同的的 binder_node。

rb_node_desc 和 rb_node_node 这两个都是红黑树节点，每一个与binder 驱动交互的进程，都会构建了两个红黑树(维护在 binder_proc 结构中)，第一个以 desc 为 key ，第二个以 binder_node 为 key。这样子 binder 驱动可以高效的以 desc 或者 node 来查找到对应的 binder_ref。

- 以 desc 查找，主要用在 client 发起事务请求。
- 以 node 查找，主要用在服务端进程发送死亡通知，引用管理等。

我这里有个疑问：refs_by_node 这个有必要吗，每一个 binder_node 不是会持有一个 refs 的hash 列表，里面保存着所有的 binder_ref 吗？

主要是使用场景，refs 这个 hash 列表用于一个一个 binder_node 节点快速查看有哪些实体引用了自己。而 refs_by_node 服务的是 binder_proc, 只需要知道 node 节点，就可以找到对应的引用信息，即查找自己引用了哪些其余的实体。

最后，death 存放的是死亡监听结构体，用于 server 死亡后发送死亡监听时提供输入信息。

