<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:94caa989b9ab569bef1cb07292acd44ecf5bcaef233a55e37856f8fe247a19e4 -->

<!-- coderabbit-ai-generated-section:v1:513423c0b6fdc9a0d0c65c1b8c2a3982aa66024fc46611c4f2b355b2c1c13e0f -->

# OmniDev CLI

Install the Python project, then use `omnidev --help`. The installed CLI supports engine startup, streaming and interactive chat, shared conversations, projects, agents, task execution and cancellation, files, terminal commands, and scoped memory. See the root README for examples. `OMNIDEV_URL` and `OMNIDEV_TOKEN` configure remote access.


<!-- /coderabbit-ai-generated:v1 -->

## Task controls

```text
omnidev tasks get 7
omnidev tasks pause 7
omnidev tasks resume 7
omnidev tasks cancel 7
```

Pause finishes the current operation before waiting. Resume uses the existing worker. Cancellation interrupts active model/tool operations. The task time budget continues during a pause. Inspect task history and files after a failure or interrupted engine restart before creating replacement work.


<!-- /coderabbit-ai-generated:v1 -->