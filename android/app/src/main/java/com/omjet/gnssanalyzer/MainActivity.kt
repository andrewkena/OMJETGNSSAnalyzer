package com.omjet.gnssanalyzer

import android.net.Uri
import android.os.Bundle
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.documentfile.provider.DocumentFile
import com.chaquo.python.Python
import com.chaquo.python.PyObject
import com.omjet.gnssanalyzer.databinding.ActivityMainBinding
import java.io.File
import java.io.FileOutputStream

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding

    private var cnbDocument: DocumentFile? = null
    private var obsDocument: DocumentFile? = null

    private val pickFolder = registerForActivityResult(
        ActivityResultContracts.OpenDocumentTree()
    ) { uri: Uri? ->
        if (uri != null) onFolderPicked(uri)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.buttonChooseFolder.setOnClickListener {
            pickFolder.launch(null)
        }

        binding.buttonAnalyze.setOnClickListener {
            runAnalysis()
        }
    }

    private fun onFolderPicked(treeUri: Uri) {
        contentResolver.takePersistableUriPermission(
            treeUri,
            android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION
        )

        val root = DocumentFile.fromTreeUri(this, treeUri)
        val cnb = root?.listFiles()?.firstOrNull {
            it.name?.endsWith(".cnb", ignoreCase = true) == true
        }

        if (cnb == null) {
            binding.textSelectedFile.text = "В выбранной папке не найден .cnb файл"
            binding.buttonAnalyze.isEnabled = false
            return
        }

        val obsName = cnb.name + ".obs"
        val obs = root.listFiles().firstOrNull { it.name == obsName }

        if (obs == null) {
            binding.textSelectedFile.text =
                "Найден ${cnb.name}, но рядом нет ${obsName} (нужен конвертированный RINEX OBS)"
            binding.buttonAnalyze.isEnabled = false
            return
        }

        cnbDocument = cnb
        obsDocument = obs
        binding.textSelectedFile.text = "Выбрано: ${cnb.name} + ${obs.name}"
        binding.buttonAnalyze.isEnabled = true
    }

    private fun runAnalysis() {
        val cnb = cnbDocument
        val obs = obsDocument
        if (cnb == null || obs == null) return

        binding.buttonAnalyze.isEnabled = false
        binding.progressBar.visibility = android.view.View.VISIBLE
        binding.progressBar.isIndeterminate = true
        binding.textStatus.text = "Анализ выполняется..."
        binding.textResult.text = ""

        Thread {
            try {
                val cnbFile = copyToCache(cnb, "mission.cnb")
                val obsFile = copyToCache(obs, "mission.cnb.obs")
                val csvOut = File(cacheDir, "photo_satellite_report.csv")

                val python = Python.getInstance()
                val module = python.getModule("mobile_pipeline")
                val result: PyObject = module.callAttr(
                    "analyze",
                    cnbFile.absolutePath,
                    obsFile.absolutePath,
                    csvOut.absolutePath
                )

                val text = formatResult(result)

                runOnUiThread {
                    binding.textResult.text = text
                    binding.textStatus.text = "Анализ завершён"
                    binding.progressBar.visibility = android.view.View.INVISIBLE
                    binding.buttonAnalyze.isEnabled = true
                }
            } catch (e: Exception) {
                runOnUiThread {
                    binding.textStatus.text = "Ошибка анализа"
                    binding.progressBar.visibility = android.view.View.INVISIBLE
                    binding.buttonAnalyze.isEnabled = true
                    Toast.makeText(this, e.message ?: "Неизвестная ошибка", Toast.LENGTH_LONG).show()
                }
            }
        }.start()
    }

    private fun copyToCache(doc: DocumentFile, targetName: String): File {
        val target = File(cacheDir, targetName)
        contentResolver.openInputStream(doc.uri)!!.use { input ->
            FileOutputStream(target).use { output ->
                input.copyTo(output)
            }
        }
        return target
    }

    private val qualityRu = mapOf(
        "EXCELLENT" to "ОТЛИЧНО",
        "GOOD" to "ХОРОШО",
        "NORMAL" to "НОРМАЛЬНО",
        "WARNING" to "ВНИМАНИЕ",
        "POOR" to "ПЛОХО"
    )

    private fun ru(value: String?): String = qualityRu[value] ?: (value ?: "-")

    private fun formatResult(result: PyObject): String {
        fun get(key: String): PyObject? = result.callAttr("get", key)
        fun str(key: String): String? = get(key)?.toString()

        return buildString {
            appendLine("ИТОГОВАЯ ОЦЕНКА   : ${ru(str("final_score"))}")
            appendLine("Качество фото     : ${ru(str("photo_quality"))}")
            appendLine("Качество GNSS     : ${ru(str("gnss_quality"))}")
            appendLine("Доля хороших фото : ${str("good_percent")}%")
            appendLine()
            appendLine("Время начала      : ${str("start_time")}")
            appendLine("Время окончания   : ${str("end_time")}")
            appendLine("Длительность      : ${str("flight_duration_min")} мин")
            appendLine("Интервал записи   : ${str("recording_interval_sec")} сек")
            appendLine("Количество фото   : ${str("photo_count")}")
            appendLine()
            appendLine("Среднее спутников : ${str("avg_satellites")}")
            appendLine("Минимум/Максимум  : ${str("min_satellites")} / ${str("max_satellites")}")
            appendLine("Уникальных        : ${str("unique_satellites")}")
            appendLine("Самая используемая группировка    : ${str("most_used_constellation")}")
            appendLine("Наименее используемая группировка : ${str("least_used_constellation")}")
            appendLine()
            appendLine("Точек траектории  : ${str("trajectory_points")}")
            appendLine("Длина траектории  : ${str("trajectory_distance_m")} м")
            appendLine("Средний PDOP      : ${str("avg_pdop")}")
            appendLine("Максимальный PDOP : ${str("max_pdop")}")
            appendLine()
            appendLine("CSV отчёт сохранён: ${str("csv_path")}")
        }
    }
}
