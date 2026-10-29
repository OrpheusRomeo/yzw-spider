<template>
  <div class="app">
    <header class="top">
      <h1>研招网爬虫控制台</h1>
      <span class="note">没有认证 —— 只在内网 / 本机用</span>
    </header>

    <main class="layout">
      <TargetForm class="left" @created="onCreated" />
      <div class="right">
        <JobPanel :job="job" />
        <ResultPanel class="results" />
      </div>
    </main>
  </div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import TargetForm from './components/TargetForm.vue'
import JobPanel from './components/JobPanel.vue'
import ResultPanel from './components/ResultPanel.vue'
import api from './api'

const job = ref(null)
let timer = null

function onCreated(created) {
  job.value = created
}

// 页面刷新之后还能看到正在跑的任务
async function loadCurrentJob() {
  try {
    const list = await api.jobs()
    if (!list || !list.length) {
      return
    }
    const running = list.find(
      (item) => item.status === 'running' || item.status === 'pending'
    )
    job.value = running || list[0]
  } catch (error) {
    // 后端还没起来就算了
  }
}

onMounted(() => {
  loadCurrentJob()
  // 状态每 2 秒刷一次
  timer = setInterval(async () => {
    if (!job.value) {
      loadCurrentJob()
      return
    }
    try {
      job.value = await api.job(job.value.id)
    } catch (error) {
      // 忽略
    }
  }, 2000)
})

onBeforeUnmount(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})
</script>

<style>
body {
  margin: 0;
  background: #f5f7fa;
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', Arial, sans-serif;
}
</style>

<style scoped>
.app {
  max-width: 1500px;
  margin: 0 auto;
  padding: 16px;
}

.top {
  display: flex;
  align-items: baseline;
  gap: 16px;
  padding: 4px 4px 16px;
}

.top h1 {
  font-size: 20px;
  margin: 0;
}

.note {
  color: #e6a23c;
  font-size: 12px;
  background: #fdf6ec;
  border: 1px solid #f5dab1;
  border-radius: 3px;
  padding: 2px 8px;
}

.layout {
  display: flex;
  gap: 16px;
  align-items: flex-start;
}

.left {
  width: 460px;
  flex: none;
}

.right {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

@media (max-width: 1100px) {
  .layout {
    flex-direction: column;
  }

  .left {
    width: 100%;
  }
}
</style>
