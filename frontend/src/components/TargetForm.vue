<template>
  <el-card shadow="never" class="panel">
    <template #header>
      <div class="card-header">
        <span class="card-title">抓取目标</span>
        <span class="card-hint">选省份 / 院校 / 专业 / 学位层次，然后点开始</span>
      </div>
    </template>

    <el-form label-width="90px" label-position="left">
      <el-form-item label="学位层次">
        <el-radio-group v-model="form.degree">
          <el-radio-button value="master">硕士</el-radio-button>
          <el-radio-button value="doctor">博士</el-radio-button>
          <el-radio-button value="both">全部</el-radio-button>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="省份">
        <el-select
          v-model="form.province"
          multiple
          collapse-tags
          collapse-tags-tooltip
          clearable
          placeholder="不选 = 全国 31 个省"
          style="width: 100%"
        >
          <el-option
            v-for="item in provinces"
            :key="item.code"
            :value="item.code"
            :label="item.name + '（' + item.count + ' 所）'"
          />
        </el-select>
      </el-form-item>

      <el-form-item label="院校">
        <el-checkbox v-model="form.schoolsAll">抓全部院校</el-checkbox>
        <el-select
          v-model="form.schoolCodes"
          multiple
          filterable
          collapse-tags
          collapse-tags-tooltip
          :disabled="form.schoolsAll"
          placeholder="不选 = 全省 / 全国全部"
          style="width: 100%; margin-top: 6px"
        >
          <el-option
            v-for="item in schools"
            :key="item.dwdm"
            :value="item.dwdm"
            :label="item.name"
          >
            <span>{{ item.name }}</span>
            <span class="option-extra">{{ item.province }}</span>
          </el-option>
        </el-select>
        <div class="field-hint">
          已选 {{ form.schoolCodes.length }} 所
          <template v-if="form.schoolCodes.length">（{{ schoolNames || '…' }}）</template>
        </div>
      </el-form-item>

      <el-form-item label="专业">
        <el-checkbox v-model="form.majorsAll">抓全部专业</el-checkbox>
        <div class="inline-row">
          <el-select
            v-model="form.majorNames"
            multiple
            filterable
            allow-create
            default-first-option
            collapse-tags
            collapse-tags-tooltip
            :disabled="form.majorsAll"
            placeholder="可以搜索，也可以直接输入专业名"
            class="grow"
          >
            <el-option-group
              v-for="group in majorGroups"
              :key="group.code"
              :label="group.name"
            >
              <el-option
                v-for="item in group.children"
                :key="item.code"
                :value="item.name"
                :label="item.name"
              />
            </el-option-group>
          </el-select>
          <el-button
            :disabled="!singleSchool || lookingMajors"
            :loading="lookingMajors"
            @click="lookupMajors"
          >
            查该校专业
          </el-button>
        </div>
        <div class="field-hint">
          <template v-if="singleSchool">按「{{ singleSchoolName }}」在研招网上的实际开设专业列一遍</template>
          <template v-else>选一所具体的院校才能查它的专业</template>
        </div>
      </el-form-item>

      <el-collapse>
        <el-collapse-item title="高级选项（限速、试跑、Excel）">
          <el-form-item label="请求间隔">
            <el-input-number v-model="form.options.delay" :min="0" :step="0.5" :precision="1" />
            <span class="unit">秒</span>
          </el-form-item>
          <el-form-item label="并发数">
            <el-input-number v-model="form.options.concurrency" :min="1" :max="8" />
            <span class="unit">研招网限流很硬，建议 1</span>
          </el-form-item>
          <el-form-item label="最多抓几所">
            <el-input-number v-model="form.options.max_schools" :min="0" :step="10" />
            <span class="unit">0 = 不限（试跑用）</span>
          </el-form-item>
          <el-form-item label="Excel">
            <el-radio-group v-model="form.options.excel">
              <el-radio-button value="auto">按数量自动</el-radio-button>
              <el-radio-button value="always">总是出</el-radio-button>
              <el-radio-button value="never">不出</el-radio-button>
            </el-radio-group>
          </el-form-item>
          <el-form-item label="Excel 上限">
            <el-input-number v-model="form.options.excel_max_schools" :min="0" :step="10" />
            <span class="unit">学校数超过就不出 Excel（CSV / JSON 不受影响）</span>
          </el-form-item>
        </el-collapse-item>
      </el-collapse>

      <el-alert
        v-if="warning"
        :title="warning"
        type="warning"
        :closable="false"
        show-icon
        class="warning"
      />

      <div class="actions">
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="submitting"
          @click="submit"
        >
          开始抓取
        </el-button>
        <el-button @click="reset">重置</el-button>
        <span v-if="lastError" class="error">{{ lastError }}</span>
      </div>
    </el-form>
  </el-card>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../api'

const emit = defineEmits(['created'])

const provinces = ref([])
const schools = ref([])
const majorGroups = ref([])

const form = reactive({
  degree: 'master',
  province: [],
  schoolsAll: true,
  schoolCodes: [],
  majorsAll: true,
  majorNames: [],
  options: {
    delay: 3,
    concurrency: 1,
    max_schools: 0,
    excel: 'auto',
    excel_max_schools: 100
  }
})

const submitting = ref(false)
const lookingMajors = ref(false)
const lastError = ref('')

// 省份变了就重新拉院校，并清掉已经选的（原来的院校可能不在新省份里）
watch(
  () => form.province.slice(),
  () => {
    form.schoolCodes = []
    loadSchools()
  }
)

const singleSchool = computed(() => {
  if (form.schoolsAll || form.schoolCodes.length !== 1) {
    return ''
  }
  return form.schoolCodes[0]
})

const singleSchoolName = computed(() => {
  const found = schools.value.find((item) => item.dwdm === singleSchool.value)
  return found ? found.name : ''
})

const schoolNames = computed(() => {
  return form.schoolCodes
    .map((code) => {
      const found = schools.value.find((item) => item.dwdm === code)
      return found ? found.name : code
    })
    .join('、')
})

// 规模提示 —— 全量跑动辄十几小时，别让人稀里糊涂就点了
const warning = computed(() => {
  if (form.schoolsAll && form.majorsAll && !form.province.length) {
    return '这是全国全量：936 所院校、几十万个专业，3 秒间隔的话大概要十几个小时，' +
      'Excel 也不会出（学校数超上限）。建议先选一个省份试试。'
  }
  if (form.schoolsAll && form.majorsAll && form.province.length > 1) {
    return '抓 ' + form.province.length + ' 个省的全部院校和全部专业，量不小。'
  }
  if (form.options.excel === 'always' && form.schoolsAll) {
    return 'Excel 设成了「总是出」，全量数据会全部攒在内存里，容易把机器撑爆。'
  }
  return ''
})

async function loadSchools() {
  try {
    const params = {}
    if (form.province.length === 1) {
      params.province = form.province[0]
    }
    schools.value = await api.schools(params)
  } catch (error) {
    schools.value = []
    ElMessage.error(error.message)
  }
}

async function lookupMajors() {
  lookingMajors.value = true
  try {
    const data = await api.majorsOfSchool(singleSchool.value)
    const names = (data.majors || []).map((item) => item.name).filter(Boolean)
    if (!names.length) {
      ElMessage.warning('没查到该校的专业')
      return
    }
    // 已经在列表里的不重复加
    const merged = form.majorNames.slice()
    names.forEach((name) => {
      if (merged.indexOf(name) < 0) {
        merged.push(name)
      }
    })
    form.majorNames = merged
    form.majorsAll = false
    const suffix = data.truncated ? '（研招网只给了 10 条，列表可能不全）' : ''
    ElMessage.success('查到 ' + names.length + ' 个专业' + suffix)
  } catch (error) {
    ElMessage.error(error.message)
  } finally {
    lookingMajors.value = false
  }
}

function reset() {
  form.degree = 'master'
  form.province = []
  form.schoolsAll = true
  form.schoolCodes = []
  form.majorsAll = true
  form.majorNames = []
  form.options.delay = 3
  form.options.concurrency = 1
  form.options.max_schools = 0
  form.options.excel = 'auto'
  form.options.excel_max_schools = 100
  lastError.value = ''
}

async function submit() {
  submitting.value = true
  lastError.value = ''
  try {
    const payload = {
      degree: form.degree,
      province: form.province,
      schools: form.schoolsAll ? [] : form.schoolCodes,
      majors: form.majorsAll ? [] : form.majorNames,
      options: {
        delay: Number(form.options.delay),
        concurrency: Number(form.options.concurrency),
        max_schools: Number(form.options.max_schools),
        excel: form.options.excel,
        excel_max_schools: Number(form.options.excel_max_schools)
      }
    }
    const job = await api.createJob(payload)
    ElMessage.success('任务已启动：' + job.id)
    emit('created', job)
  } catch (error) {
    lastError.value = error.message
    ElMessage.error(error.message)
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  try {
    provinces.value = await api.provinces()
  } catch (error) {
    ElMessage.error(error.message)
  }
  loadSchools()

  // 专业代码表可能还没缓存，第一次会慢一点
  try {
    majorGroups.value = await api.majors()
  } catch (error) {
    majorGroups.value = []
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
.field-hint,
.unit,
.option-extra {
  color: #909399;
  font-size: 12px;
}

.field-hint {
  margin-top: 4px;
  line-height: 1.5;
}

.inline-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.grow {
  flex: 1;
}

.unit {
  margin-left: 8px;
}

.option-extra {
  float: right;
}

.warning {
  margin: 12px 0;
}

.actions {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.error {
  color: #f56c6c;
  font-size: 13px;
}
</style>
