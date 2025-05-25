# Getting Started to Mastery in Chromium

> 本文总阅读量 <span id="busuanzi_value_page_pv"><i class="fa fa-spinner fa-spin"></i></span>次

This is an introduction to the learning route of Chromium. I believe that when learning anything, speed is essential. 
One must never procrastinate or give oneself too much time. Next, we will use a period of two months to help you gain a deeper understanding of Chromium.  

## Week 1-2

At this stage, you don't need to understand everything. What you need to do is to know and memorize. You can even recite it like children do during morning reading to help you remember. 

1. Basic Principles of Browser Operation [Reference](https://blog.poetries.top/browser-working-principle/)
    - Have knowledge of the overall architecture of browsers.
    - Understand the entire process from entering a URL to page rendering.
    - Be aware of the module structure and functions of the Chromium project.

2. Chromium Design Documents and Source Code
    - Overview
        - [Overview](https://www.chromium.org/Home/)
    - Source Code
        - [Code Search Online](https://source.chromium.org/chromium/chromium/src)
    - Multi - Threaded Architecture
        - [Multi - Process Architecture](https://www.chromium.org/developers/design-documents/multi-process-architecture/)
    - Blink
        - [How Blink works](https://docs.google.com/document/d/1aitSOucL0VHZa9Z2vbRJSyAIsAz24kX8LFByQ5xQnUg/edit?tab=t.0#heading=h.v5plba74lfde)
        - [LIFE OF A pixel](https://docs.google.com/presentation/d/1boPxbgNrTU0ddsc144rcXayGA_WF53k96imRH8Mp34Y/edit#slide=id.ga884fe665f_64_6)
    - IPC
        - [Inter - Process Communication](https://www.chromium.org/developers/design-documents/inter-process-communication/)

3. Local Compilation of Chromium
    - Checkout, Build, & Run Chromium
        - [Documentation](https://www.chromium.org/developers/how-tos/get-the-code/) 


## Week 3-6

In the next stage, the difficulty will increase. I believe that in the previous two weeks, we've formed some initial understandings and accumulated some questions. The next four weeks will be used to correct your initial understandings and solve your problems. During this period, we need to conduct in-depth learning on the architecture of the browser itself, and carry out in-depth exploration of the main process, rendering process, GPU process, inter process communication, and the sandbox mechanism. 

1. Browser Main Process
    - Research the role of the browser process in managing the interface, coordinating processes, and handling user input.

2. Rendering Process
    - Processes such as HTML parsing, CSS style calculation, layout calculation, and painting.

3. Network Process
    - How the network process handles network - related tasks such as HTTP requests, DNS resolution, and connection management.

4. GPU Process
    - Understand the role of the GPU process in accelerating graphics rendering. Learn basic concepts of graphics processing, such as rasterization and composition.

5. IPC (Inter - Process Communication)
    - How different processes communicate with each other through IPC.

6. Sandbox Mechanism
    - Understand Chromium's sandbox technology and how it enhances browser security by restricting the permissions of the rendering process and plugin processes.

7. Analysis of Inter - module Collaboration
    - Analyze once again the process from entering a URL to page rendering.


## Week 7-8

In the previous few weeks of learning, we've been exposed to some details of the source code. In the following time, we need to conduct a more detailed analysis of the source code for the modules that interest us.

1. Master the techniques of reading the source code of large-scale projects.
2. Try to modify the modules that you are interested in.
3. Contribute to the open-source community. 

