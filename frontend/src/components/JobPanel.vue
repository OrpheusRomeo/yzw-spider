<template>
  <el-card shadow="never" class="panel">
    <template #header>
      <div class="card-header">
        <span class="card-title">任务</span>
        <span class="card-hint" v-if="job">{{ job.id }}</span>
      </div>
    </template>

    <div v-if="!job" class="empty">
      还没有任务。在左边选好目标，点「开始抓取」。
    </div>

    <template v-else>
      <div class="status-row">
        <el-tag :type="statusType" size="large">{{ statusText }}</el-tag>
        <span class="counter">已抓 <b>{{ job.items || 0 }}</b> 条</span>
        <span class="counter">院校 <b>{{ job.schools_done || 0 }}</b> 所</span>
        <span class="counter">耗时 <b>{{ elapsed }}</b></span>
        <el-button
          v-if="running"
          type="danger"
          plain
          size="small"
          :loading="stopping"
          @click="stop"
        >
          停止
        </el-button>
      </div>

      <div class="detail-row" v-if="degreeText">
        <span>{{ degreeText }}</span>
        <span v-if="job.current_school">当前：{{ job.current_school }}</span>
        <span v-if="job.exit_code !== null && job.exit_code !== undefined">
          退出码 {{ job.exit_code }}
        </span>
      </div>

      <el-alert
        v-if="job.message"
        :title="job.message"
        type="error"
        :closable="false"
        show-icon
        class="message"
      />

      <div ref="logBox" class="log-box">
        <pre class="log">{{ logText }}</pre>
      </div>
    </template>
  </el-card>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const props = defineProps({
  job: { type: Object, default: null }
})

// 日志最多留这么多行，再多就把最前面的丢掉
const MAX_LINES = 2000
const POLL_MS = 2000

const lines = ref([])
const offset = ref(0)
const stopping = ref(false)
const logBox = ref(null)
let timer = null

const running = computed(() => {
  return props.job && (props.job.status === 'running' || props.job.status === 'pending')
})

const statusText = computed(() => {
  const map = {
    pending: '排队中',
    running: '抓取中',
    done: '已完成',
    stopped: '已停止',
    failed: '失败',
    interrupted: '已中断'
  }
  return props.job ? map[props.job.status] || props.job.status : ''
})

const statusType = computed(() => {
  const map = {
    pending: 'info',
    running: 'primary',
    done: 'success',
    stopped: 'warning',
    failed: 'danger',
    interrupted: 'warning'
  }
  return props.job ? map[props.job.status] || 'info' : 'info'
})

const degreeText = computed(() => {
  if (!props.job) {
    return ''
  }
  const degree = { master: '硕士', doctor: '博士', both: '硕士 + 博士' }
  const parts = []
  parts.push(degree[props.job.degree] || props.job.degree)
  if (props.job.province && props.job.province.length) {
    parts.push('省份 ' + props.job.province.join('、'))
  } else {
    parts.push('全国')
  }
  if (props.job.schools && props.job.schools.length) {
    parts.push('指定院校')
  } else {
    parts.push('全部院校')
  }
  if (props.job.majors && props.job.majors.length) {
    parts.push('指定专业')
  } else {
    parts.push('全部专业')
  }
  return parts.join(' · ')
})

const elapsed = computed(() => {
  if (!props.job || !props.job.started_at) {
    return '-'
  }
  const start = parseTime(props.job.started_at)
  const end = props.job.finished_at ? parseTime(props.job.finished_at) : Date.now()
  if (!start) {
    return '-'
  }
  const seconds = Math.max(0, Math.round((end - start) / 1000))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = seconds % 60
  if (hours) {
    return hours + ' 小时 ' + minutes + ' 分'
  }
  if (minutes) {
    return minutes + ' 分 ' + rest + ' 秒'
  }
  return rest + ' 秒'
})

const logText = computed(() => lines.value.join('\n'))

function parseTime(text) {
  if (!text) {
    return 0
  }
  // '2026-10-29 17:00:00' -> Date，Safari 不认 '-' 分隔，得换成 '/'
  const value = new Date(String(text).replace(/-/g, '/')).getTime()
  return isNaN(value) ? 0 : value
}

// 换了任务就从头读日志
watch(
  () => (props.job ? props.job.id : ''),
  () => {
    lines.value = []
    offset.value = 0
    if (props.job) {
      poll()
    }
  }
)

async function poll() {
  if (!props.job) {
    return
  }
  try {
    const chunk = await api.logs(props.job.id, offset.value, 500)
    if (chunk && chunk.lines && chunk.lines.length) {
      lines.value = lines.value.concat(chunk.lines)
      if (lines.value.length > MAX_LINES) {
        lines.value = lines.value.slice(lines.value.length - MAX_LINES)
      }
      offset.value = chunk.next_offset
      scrollToBottom()
    }
  } catch (error) {
    // 日志读失败不用打断页面，状态那边还会继续轮询
  }
}

function scrollToBottom() {
  nextTick(() => {
    if (logBox.value) {
      logBox.value.scrollTop = logBox.value.scrollHeight
    }
  })
}

async function stop() {
  if (!props.job) {
    return
  }
  stopping.value = true
  try {
    await api.stopJob(props.job.id)
    ElMessage.info('正在停止…')
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    stopping.value = false
  }
}

onMounted(() => {
  poll()
  timer = setInterval(poll, POLL_MS)
})

onBeforeUnmount(() => {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
})
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.card-title {
  font-weight: 600;
}

.card-hint,
.counter,
.detail-row {
  color: #606266;
  font-size: 13px;
}

.empty {
  color: #909399;
  padding: 24px 0;
  text-align: center;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.counter b {
  color: #303133;
}

.detail-row {
  display: flex;
  gap: 16px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.message {
  margin-top: 12px;
}

.log-box {
  margin-top: 12px;
  height: 320px;
  overflow: auto;
  background: #1e1e1e;
  border-radius: 4px;
  padding: 10px 12px;
}

.log {
  margin: 0;
  color: #dcdcdc;
  font-family: 'Cascadia Mono', Consolas, 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
