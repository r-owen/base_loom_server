// value is replaced by python code
const TranslationDict = { translation_dict }

const MaxFiles = 10

const MinBlockSize = 11
const MaxBlockSize = 21

// Display gap on left and right edges of threading end numbers
const ThreadingWidthGap = 5

// Diplay gap between top of end color bar/outline rectangle and bottom of end number
const ThreadingEndTopGap = 10

const ThreadedAlpha = 0.8
const UnthreadedAlpha = 0.3

// Display gap on left and right edges of warp and top and bottom edges of weft thread
const WeavingThreadDisplayGap = 1

const WeavingThreadHalfWidth = 10

const ShaftRaisedHeight = 20
const ShaftLoweredHeight = 5
const ShaftMinWidth = 5
const ShaftMaxWidth = 21
const ShaftSeparation = 2

const NullDirectionData = {
    "forward": null,
}

const NullEndData = {
    "total_end_number0": null,
    "total_end_number1": null,
    "end_number0": null,
    "end_number1": null,
    "end_repeat_number": null,
}

const NullPickData = {
    "total_pick_number": null,
    "pick_number": null,
    "pick_repeat_number": null,
}

const NullSeparateData = {
    "separate": null,
}

const ConnectionStateEnum = {
    "DISCONNECTED": 0,
    "CONNECTED": 1,
    "CONNECTING": 2,
    "DISCONNECTING": 3,
}

/* Keys are ConnectionStateEnum values, names are translated names */
let ConnectionStateTranslationDict = {}
for (let itemName of Object.keys(ConnectionStateEnum)) {
    let intValue = ConnectionStateEnum[itemName]
    ConnectionStateTranslationDict[intValue] = t(itemName.toLowerCase())
}
Object.freeze(ConnectionStateTranslationDict)

const NullConnectionState = {
    "state": ConnectionStateEnum.DISCONNECTED,
    "reason": "",
}

const DirectionControlEnum = {
    "FULL": 1,
    "LOOM": 2,
    "SOFTWARE": 3,
}

const ModeEnum = {
    "WEAVING": 1,
    "THREADING": 2,
    "SETTINGS": 3,
}

const SeverityColors = {
    1: null,
    2: "yellow",
    3: "red",
}

const SeverityEnum = {
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 3,
}

const ShaftStateEnum = {
    UNKNOWN: 0,
    DONE: 1,
    MOVING: 2,
    ERROR: 3,
}

const ShaftStateTranslationDict = {
    0: t("?"),
    1: "",  // Done is not displayed, so no translation needed
    2: t("Moving"),
    3: t("Error"),
}

const NullShaftStateData = {
    "state": ShaftStateEnum.UNKNOWN,
    "shaft_word": 0,
}

/* Return the largest odd integer <= rounded value

The description isn't quite right for negative values;
those are first truncated towards 0, then made more negative if needed.
*/
function asOddDecreased(value) {
    let ret = Math.round(value)
    return ret % 2 == 0 ? ret - 1 : ret
}

/* Return the largest odd integer >= rounded value

The description isn't quite right for negative values;
those are first truncated towards 0, then made more positive if needed.
*/
function asOddIncreased(value) {
    let ret = Math.round(value)
    return ret % 2 == 0 ? ret + 1 : ret
}

/*
Compare the names of two Files, taking numbers into account.

To sort file names in a FileList you must first 
convert the FileList to an Array::

    // myFileList is a FileList (which cannot be sorted)
    fileArr = Array.from(myFileList)
    fileArr.sort(compareFiles)
*/
const numericCollator = new Intl.Collator(undefined, { numeric: true })
function compareFiles(a, b) {
    // 
    return numericCollator.compare(a.name, b.name)
}

/*
Handle websocket close
*/
async function handleWebsocketClosed(event) {
    let statusElt = document.getElementById("status")
    statusElt.textContent = t("lost connection to server") + `: ${event.reason} `
    statusElt.style.color = "red"
}

/*
Return null if value is "", else return an int as a bool
*/
function asBooleanOrNull(value) {
    return value == "" ? null : Boolean(parseInt(value))
}

/*
Return null if value is "", else return parseInt(value)
*/
function asIntOrNull(value) {
    return value == "" ? null : parseInt(value)
}

/*
Return defaultValue (defaults to "") if value is null, else return value
*/
function nullToDefault(value, defaultValue = "") {
    return value == null ? defaultValue : value
}

function preventDefaults(event) {
    event.preventDefault()
    event.stopPropagation()
}

/*
Read a binary file and encode it using base64

The encoding algorithm is from https://stackoverflow.com/a/58339391/1653413
*/
function readAndEncodeBinaryFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader()

        reader.onload = res => {
            resolve(res.target.result.split(',')[1])
        }
        reader.onerror = err => reject(err)

        reader.readAsDataURL(file)
    })
}

/*
Async wrapper around FileReader.readAsText

from https://masteringjs.io/tutorials/fundamentals/filereader#:~:text=The%20FileReader%20class%27%20async%20API%20isn%27t%20ideal,for%20usage%20with%20async%2Fawait%20or%20promise%20chaining.
*/
function readTextFile(file, encoding = "utf-8") {
    return new Promise((resolve, reject) => {
        const reader = new FileReader()

        reader.onload = res => {
            resolve(res.target.result)
        }
        reader.onerror = err => reject(err)

        reader.readAsText(file)
    })
}

/* Translate a phrase using TranslationDict */
function t(phrase) {
    if (!(phrase in TranslationDict)) {
        console.warn(`Missing translation key: "${phrase}"`)
        return phrase
    }
    return TranslationDict[phrase]
}

/*
Return a truncated version of a string with appended "..."

or the original string if it is short enough.
*/
function truncateStr(value, maxLength = 100) {
    if (value.length > maxLength) {
        return value.slice(0, maxLength - 3) + "..."
    } else {
        return value
    }
}


/*
A class similar to Python asyncio.Future, but with an optional timeout

The main design is from https://stackoverflow.com/a/72280546/1653413
*/
class Future {
    constructor(description, timeoutMs = 0) {
        this.description = description
        this.result = undefined
        this.exception = undefined
        this.done = false
        this.success = () => { }
        this.fail = () => { }
        if (timeoutMs > 0) {
            setTimeout(this.timeout.bind(this), timeoutMs)
        }
    }
    setResult(result) {
        if (this.done) {
            throw Error("Already done")
        }
        this.result = result
        this.done = true

        this.success(this.result)
    }
    setException(exception) {
        if (this.done) {
            throw Error("Already done")
        }
        this.exception = exception
        this.done = true

        this.fail(this.exception)
    }
    then(success, fail) {
        this.success = success
        this.fail = fail
    }
    timeout() {
        if (this.done) {
            return
        }
        this.setException(new TimeoutError(`${this.description} timed out`))
    }
}

/*
A minimal weaving pattern, including display code.

Javascript version of the python class of the same name,
with the same attributes but different methods.

Args:
    datadict: Data from a Python ReducedPattern dataclass.
*/
class ReducedPattern {
    constructor(datadict) {
        this.name = datadict.name
        this.color_table = datadict.color_table
        this.warp_colors = datadict.warp_colors
        this.threading = datadict.threading
        this.picks = []
        this.end_number0 = datadict.end_number0
        this.end_number1 = datadict.end_number1
        this.repeat_end_number = datadict.repeat_end_number
        for (let pickdata of datadict.picks) {
            this.picks.push(new Pick(pickdata))
        }
    }
}

/*
Data for a pick
*/
class Pick {
    constructor(datadict) {
        this.color = datadict.color
        this.shaft_word = BigInt(datadict.shaft_word)
    }
}

class TimeoutError extends Error {
    constructor(message) {
        super(message)
        this.name = "TimeoutError"
    }
}

class LoomClient {
    constructor() {
        // Save the background color in order to restore it after drag-and-drop
        this.backgroundColor = window.getComputedStyle(document.body).getPropertyValue("background-color")
        // Dict of command type: Future for commands that were run with sendCommandAndWait
        this.commandFutures = {}
        this.currentPattern = null
        this.loomConnectionState = NullConnectionState
        this.statusMessage = null
        this.currentEndData = NullEndData
        this.currentPickData = NullPickData
        this.direction = NullDirectionData
        this.jumpEndData = NullEndData
        this.jumpPickData = NullPickData
        this.separateThreadingRepeatsData = NullSeparateData
        this.separateWeavingRepeatsData = NullSeparateData
        this.threadGroupSize = 4
        this.loomInfo = null
        this.settings = null
        this.shaftState = NullShaftStateData
        this.weaveForward = true
        this.ws = new WebSocket("ws")
    }

    init() {
        this.ws.onmessage = this.handleServerReply.bind(this)
        this.ws.onclose = handleWebsocketClosed

        const isDarkMode = window.matchMedia('(prefers-color-scheme: dark)')
        isDarkMode.addEventListener("change", this.handleDarkLightTheme.bind(this))

        let debugChangeDirectionButton = document.getElementById("debug_change_direction")
        debugChangeDirectionButton.addEventListener("click", this.handleDebugChangeDirection.bind(this))

        let debugCloseConnectionButton = document.getElementById("debug_close_connection")
        debugCloseConnectionButton.addEventListener("click", this.handleDebugCloseConnection.bind(this))

        let debugHideButton = document.getElementById("debug_hide")
        debugHideButton.addEventListener("click", this.handleDebugHide.bind(this))

        let debugNextPickButton = document.getElementById("debug_next_pick")
        debugNextPickButton.addEventListener("click", this.handleDebugNextPick.bind(this))

        let groupSizeElt = document.getElementById("thread_group_size")
        groupSizeElt.addEventListener("change", this.handleThreadGroupSize.bind(this))

        let jumpToEndForm = document.getElementById("jump_to_end_form")
        jumpToEndForm.addEventListener("submit", this.handleJumpToEndSubmit.bind(this))

        let jumpToEndResetElt = document.getElementById("jump_to_end_reset")
        jumpToEndResetElt.addEventListener("click", this.handleJumpToEndReset.bind(this))

        let jumpToPickForm = document.getElementById("jump_to_pick_form")
        jumpToPickForm.addEventListener("submit", this.handleJumpToPickSubmit.bind(this))

        let jumpToPickResetElt = document.getElementById("jump_to_pick_reset")
        jumpToPickResetElt.addEventListener("click", this.handleJumpToPickReset.bind(this))

        let jumpTotalEndNumber0Elt = document.getElementById("jump_total_end_number0")
        // Select all text on focus, to make it easier to try different jump values
        // (without this, you are likely to append digits, which is rarely what you want)
        jumpTotalEndNumber0Elt.addEventListener("focus", this.selectOnInput.bind(this, jumpTotalEndNumber0Elt))
        jumpTotalEndNumber0Elt.addEventListener("input", this.handleJumpToEndInput.bind(this))

        let jumpTotalPickNumberElt = document.getElementById("jump_total_pick_number")
        jumpTotalPickNumberElt.addEventListener("focus", this.selectOnInput.bind(this, jumpTotalPickNumberElt))
        jumpTotalPickNumberElt.addEventListener("input", this.handleJumpToPickInput.bind(this))

        let loomNameInputElt = document.getElementById("setting_loom_name_input")
        // Select all text on focus, to make it easier to type a new name
        // (without this, you are likely to append to the existing name, instead of replacing it).
        loomNameInputElt.addEventListener("focus", this.selectOnInput.bind(this, loomNameInputElt))
        loomNameInputElt.addEventListener("input", this.handleLoomNameInput.bind(this))

        let loomNameResetButton = document.getElementById("setting_loom_name_reset")
        loomNameResetButton.addEventListener("click", this.handleSettingsReset.bind(this))

        let separateThreadingRepeatsCheckbox = document.getElementById("separate_threading_repeats")
        separateThreadingRepeatsCheckbox.addEventListener("change", this.handleSeparateRepeats.bind(this, true))

        let separateWeavingRepeatsCheckbox = document.getElementById("separate_weaving_repeats")
        separateWeavingRepeatsCheckbox.addEventListener("change", this.handleSeparateRepeats.bind(this, false))

        let settingLanguageElt = document.getElementById("setting_language")
        settingLanguageElt.addEventListener("change", this.sendSettings.bind(this))

        let settingDirectionControlElt = document.getElementById("setting_direction_control")
        settingDirectionControlElt.addEventListener("change", this.sendSettings.bind(this))

        let settingLoomNameForm = document.getElementById("setting_loom_name_form")
        settingLoomNameForm.addEventListener("submit", this.sendSettings.bind(this))

        let settingEnd1OnRightElt = document.getElementById("setting_end1_on_right")
        settingEnd1OnRightElt.addEventListener("change", this.sendSettings.bind(this))

        let settingThreadBackToFrontElt = document.getElementById("setting_thread_back_to_front")
        settingThreadBackToFrontElt.addEventListener("change", this.sendSettings.bind(this))

        let settingThreadRightToLeftElt = document.getElementById("setting_thread_right_to_left")
        settingThreadRightToLeftElt.addEventListener("change", this.sendSettings.bind(this))

        let settingThreadGroupSizeElt = document.getElementById("setting_thread_group_size")
        settingThreadGroupSizeElt.addEventListener("change", this.sendSettings.bind(this))

        let tabThreadingElt = document.getElementById("mode_threading")
        tabThreadingElt.addEventListener("click", this.handleMode.bind(this, ModeEnum.THREADING))

        let tabSettingsElt = document.getElementById("mode_settings")
        tabSettingsElt.addEventListener("click", this.handleMode.bind(this, ModeEnum.SETTINGS))

        let tabWeavingElt = document.getElementById("mode_weaving")
        tabWeavingElt.addEventListener("click", this.handleMode.bind(this, ModeEnum.WEAVING))

        let threadDirectionElt = document.getElementById("thread_direction")
        threadDirectionElt.addEventListener("click", this.handleToggleDirection.bind(this))

        // Assign event handlers for file upload drag-and-drop.
        // Use the entire body as the drop area.
        const uploadDropAreaElt = document.body;
        ["dragenter", "dragover", "dragleave", "drop"].forEach(eventName => {
            uploadDropAreaElt.addEventListener(eventName, preventDefaults)
        });
        ["dragenter", "dragover"].forEach(eventName => {
            uploadDropAreaElt.addEventListener(eventName, this.setBackgroundColor.bind(this, uploadDropAreaElt, "#E6E6FA"))
        });
        ["dragleave", "drop"].forEach(eventName => {
            uploadDropAreaElt.addEventListener(eventName, this.setBackgroundColor.bind(this, uploadDropAreaElt, this.backgroundColor))
        })
        uploadDropAreaElt.addEventListener("drop", this.handleUploadDrop.bind(this))

        let uploadFileButton = document.getElementById("upload_file_button")
        uploadFileButton.addEventListener("click", this.handleUploadButton.bind(this))

        let uploadFileInputElt = document.getElementById("upload_file_input")
        uploadFileInputElt.addEventListener("change", this.handleUploadFileInput.bind(this))

        let weaveDirectionElt = document.getElementById("weave_direction")
        weaveDirectionElt.addEventListener("click", this.handleToggleDirection.bind(this))
        let patternMenu = document.getElementById("pattern_menu")
        patternMenu.addEventListener("change", this.handlePatternMenu.bind(this))

        this.handleDarkLightTheme()

        screen.orientation.addEventListener("change", this.displayCanvases.bind(this))
        window.addEventListener("resize", (this.displayCanvases.bind(this)))
    }

    /*
    Display the canvases that should be visible
    */
    displayCanvases(event) {
        if (this.mode != ModeEnum.SETTINGS) {
            this.displayShaftState()
        }
        if (this.mode == ModeEnum.THREADING) {
            this.displayThreadingPattern(event)
        } else if (this.mode == ModeEnum.WEAVING) {
            this.displayWeavingPattern(event)
        }
    }

    /*
    Display threading and weaving direction (thread/unthread, weave/unweave).
    */
    displayDirection() {
        if (!this.settings) {
            return
        }
        let threadDirectionElt = document.getElementById("thread_direction")
        let weaveDirectionElt = document.getElementById("weave_direction")
        let threadArrowPointsLeft = this.settings.thread_right_to_left
        if (!this.direction.forward) {
            threadArrowPointsLeft = !threadArrowPointsLeft
        }
        const threadArrow = threadArrowPointsLeft ? "←" : "→"

        if (this.direction.forward) {
            threadDirectionElt.textContent = `${threadArrow} ${t("Thread")}`
            weaveDirectionElt.textContent = t("Weave")
            threadDirectionElt.classList.remove("direction_undo")
            weaveDirectionElt.classList.remove("direction_undo")
            threadDirectionElt.classList.add("direction_do")
            weaveDirectionElt.classList.add("direction_do")
        } else {
            threadDirectionElt.textContent = `${threadArrow} ${t("Unthread")}`
            weaveDirectionElt.textContent = t("Unweave")
            threadDirectionElt.classList.remove("direction_do")
            weaveDirectionElt.classList.remove("direction_do")
            threadDirectionElt.classList.add("direction_undo")
            weaveDirectionElt.classList.add("direction_undo")
        }
    }

    /*
    Display the current end numbers.
    */
    displayEnds() {
        let totalEndNumber0Elt = document.getElementById("total_end_number0")
        let totalEndNumber1Elt = document.getElementById("total_end_number1")
        let endNumber0Elt = document.getElementById("end_number0")
        let endNumber1Elt = document.getElementById("end_number1")
        let endsPerRepeatElt = document.getElementById("ends_per_repeat")
        let repeatNumberElt = document.getElementById("end_repeat_number")
        if (!this.currentPattern) {
            this.currentEndData = NullEndData
        }
        totalEndNumber0Elt.textContent = nullToDefault(this.currentEndData.total_end_number0)
        totalEndNumber1Elt.textContent = nullToDefault(this.currentEndData.total_end_number1)
        endNumber0Elt.textContent = "(" + nullToDefault(this.currentEndData.end_number0)
        endNumber1Elt.textContent = nullToDefault(this.currentEndData.end_number1)
        endsPerRepeatElt.textContent = nullToDefault(this.currentPattern.threading.length, "?") + ","
        repeatNumberElt.textContent = nullToDefault(this.currentEndData.end_repeat_number) + ")"
    }

    /*
    Display the jump end and repeat
    */
    displayJumpEnd() {
        let endNumber0Elt = document.getElementById("jump_total_end_number0")
        if (!this.currentPattern) {
            this.jumpEndData = NullPickData
        }
        endNumber0Elt.value = nullToDefault(this.jumpEndData.total_end_number0)
        if (this.currentPattern) {
            this.displayThreadingPattern()
        }
        this.handleJumpToEndInput(null)
    }

    /*
    Display the jump pick and repeat
    */
    displayJumpPick() {
        let totalPickNumberElt = document.getElementById("jump_total_pick_number")
        if (!this.currentPattern) {
            this.jumpPickNumber = NullPickData
        }
        totalPickNumberElt.value = nullToDefault(this.jumpPickNumber.total_pick_number)
        if (this.currentPattern) {
            this.displayWeavingPattern()
        }
        this.handleJumpToPickInput(null)
    }

    /*
    Display a list of language names the Language menu in the Settings panel.

    The argument is a list of language names.
    */
    displayLanguageNames(languages) {
        let settingLanguageElt = document.getElementById("setting_language")

        // Purge existing items
        while (settingLanguageElt.options.length > 0) {
            select.remove(0)
        }

        // Add new items
        for (let language of languages) {
            let option = new Option(language)
            settingLanguageElt.options.add(option)
        }
    }

    displayLoomInfo() {
        let loominfoElt = document.getElementById("loom_info")
        const nodata = (this.loomInfo == null) || (this.settings == null)
        const msg = nodata ? "" : `${this.settings.loom_name} ${this.loomInfo.num_shafts}`
        loominfoElt.textContent = msg
        document.title = msg
        if (this.loomInfo != null) {
            let debugDivElt = document.getElementById("debug_div")
            debugDivElt.style.display = this.loomInfo.is_mock ? "block" : "none"
        }
    }

    /*
    Display the current mode
    */
    displayMode() {
        // Get all elements with class="tablinks" and remove the class "active"
        let buttons = document.getElementsByClassName("tab_button")
        for (let button of buttons) {
            button.classList.remove("tab_active")
        }

        let elt = null
        let modeButton = null
        if (this.mode == ModeEnum.WEAVING) {
            // weaving
            modeButton = document.getElementById("mode_weaving")
            for (const elt of document.getElementsByClassName("threading-flex")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("threading-grid")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("settings-flex")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("not-settings-flex")) {
                elt.style.display = "flex"
            }
            for (const elt of document.getElementsByClassName("weaving-flex")) {
                elt.style.display = "flex"
            }
            for (const elt of document.getElementsByClassName("weaving-grid")) {
                elt.style.display = "grid"
            }
            this.displayWeavingPattern()
        } else if (this.mode == ModeEnum.THREADING) {
            modeButton = document.getElementById("mode_threading")
            for (const elt of document.getElementsByClassName("weaving-flex")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("weaving-grid")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("settings-flex")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("not-settings-flex")) {
                elt.style.display = "flex"
            }
            for (const elt of document.getElementsByClassName("threading-flex")) {
                elt.style.display = "flex"
            }
            for (const elt of document.getElementsByClassName("threading-grid")) {
                elt.style.display = "grid"
            }
            this.displayDirection()  // to show correct direction arrow
            this.displayThreadingPattern()
        } else if (this.mode == ModeEnum.SETTINGS) {
            modeButton = document.getElementById("mode_settings")
            for (const elt of document.getElementsByClassName("weaving-flex")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("weaving-grid")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("threading-flex")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("threading-grid")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("not-settings-flex")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("settings-flex")) {
                elt.style.display = "flex"
            }
        } else {
            console.warn("Unrecognized mode", this.mode)
        }
        if (modeButton != null) {
            modeButton.classList.add("tab_active")
        }
    }

    /*
    Display the current pick and repeat.
    */
    displayPick() {
        let totalPicksElt = document.getElementById("total_pick_number")
        let pickNumberElt = document.getElementById("pick_number")
        let picksPerRepeatElt = document.getElementById("picks_per_repeat")
        let repeatNumberElt = document.getElementById("pick_repeat_number")
        if (!this.currentPattern) {
            this.currentPickData = NullPickData
        }
        totalPicksElt.textContent = nullToDefault(this.currentPickData.total_pick_number)
        pickNumberElt.textContent = "(" + nullToDefault(this.currentPickData.pick_number)
        picksPerRepeatElt.textContent = nullToDefault(this.currentPattern.picks.length, "?") + ","
        repeatNumberElt.textContent = nullToDefault(this.currentPickData.pick_repeat_number) + ")"
    }

    /*
    * Display Settings
    */
    displaySettings() {
        let loomNameInputElt = document.getElementById("setting_loom_name_input")
        const loomNameHasFocus = document.activeElement == loomNameInputElt
        loomNameInputElt.value = this.settings.loom_name

        let langaugesMenu = document.getElementById("setting_language")
        if (this.settings != null) {
            langaugesMenu.value = this.settings.language
        }

        let directionControlDiv = document.getElementById("setting_direction_control_div")
        let directionControlElt = document.getElementById("setting_direction_control")
        if (this.settings.direction_control == DirectionControlEnum.FULL) {
            directionControlDiv.style.display = "none"
            directionControlElt.value = null
        } else {
            directionControlElt.value = this.settings.direction_control
            directionControlDiv.style.display = "flex"
        }
        let end1OnRightElt = document.getElementById("setting_end1_on_right")
        end1OnRightElt.value = this.settings.end1_on_right ? "1" : "0"
        let threadRightToLeftElt = document.getElementById("setting_thread_right_to_left")
        threadRightToLeftElt.value = this.settings.thread_right_to_left ? "1" : "0"
        let threadBackToFrontElt = document.getElementById("setting_thread_back_to_front")
        threadBackToFrontElt.value = this.settings.thread_back_to_front ? "1" : "0"
        let defaultThreadGroupSize = document.getElementById("setting_thread_group_size")
        defaultThreadGroupSize.value = this.settings.thread_group_size
        let weaveDirectionElt = document.getElementById("weave_direction")
        let threadDirectionElt = document.getElementById("thread_direction")
        if (this.settings.direction_control == DirectionControlEnum.LOOM) {
            weaveDirectionElt.disabled = true
            threadDirectionElt.disabled = true
        } else {
            weaveDirectionElt.disabled = false
            threadDirectionElt.disabled = false
        }
        this.handleLoomNameInput()
        if (loomNameHasFocus) {
            loomNameInputElt.select()
        }
        this.displayLoomInfo()
    }

    /*
    Display shaft state on the "shafts_canvas" element.
    */
    displayShaftState() {
        if ((this.mode == ModeEnum.SETTINGS) || (this.loomInfo == null)) {
            return
        }
        let canvas = document.getElementById("shafts_canvas")

        // Make resizing work better,
        // and, in the case of height, prevent the height growing with each new shed.
        canvas.width = 100

        let ctx = canvas.getContext("2d")
        ctx.clearRect(0, 0, canvas.width, canvas.height)

        let rect = document.getElementById("shafts_canvas_container").getBoundingClientRect()

        const availableWidth = asOddDecreased(rect.width)

        // Measure space required for the max shaft number -- 2 digits.
        // We could measure the space required for shaft "1" separately, but keep it simple.
        const endLabelElt = document.getElementById("end_label")
        const font = window.getComputedStyle(endLabelElt).font
        ctx.font = font  // For initial measurements to set size; set again later after setting size
        const fontMeas = ctx.measureText("32")
        const fontHeight = asOddIncreased(fontMeas.fontBoundingBoxAscent + fontMeas.fontBoundingBoxDescent)
        const fontHalfHeight = (fontHeight + 1) / 2
        const fontHalfWidth = asOddIncreased((fontMeas.actualBoundingBoxLeft + fontMeas.actualBoundingBoxRight) / 2)

        const availableBlockWidth = ((availableWidth - (2 * fontHalfWidth)) / (this.loomInfo.num_shafts - 1)) - ShaftSeparation
        const blockWidth = asOddDecreased(Math.max(ShaftMinWidth, Math.min(ShaftMaxWidth, availableBlockWidth)))
        const blockAndSepWidth = blockWidth + ShaftSeparation

        canvas.width = this.loomInfo.num_shafts * blockAndSepWidth + 4 // 4 avoids cutoff at the right
        canvas.height = Math.max(ShaftRaisedHeight, fontHeight) + fontHeight

        const isDarkMode = window.matchMedia('(prefers-color-scheme: dark)')
        ctx.fillStyle = isDarkMode.matches ? "#ffffff" : "#000000"

        // Set the font again, now that the canvas size has been set 
        ctx.font = font
        // Set properties such that the position for fillText is the center of the text
        ctx.textBaseline = "middle"
        ctx.textAlign = "center"

        const firstBlockStartX = Math.floor(ShaftSeparation / 2)
        let bitmask = BigInt(this.shaftState.shaft_word)
        if (this.shaftState.state == ShaftStateEnum.DONE) {
            // Display shaft numbers 1, 4, 8, ...
            const firstBlockCenterX = Math.floor((ShaftSeparation + blockWidth) / 2)
            for (let shaftIndex = 0; shaftIndex < this.loomInfo.num_shafts; shaftIndex++) {
                const shaftNum = shaftIndex + 1
                if ((shaftNum % 4 == 0) || (shaftNum == 1)) {
                    ctx.fillText(
                        shaftNum,
                        firstBlockCenterX + (blockAndSepWidth * shaftIndex),
                        canvas.height - fontHalfHeight,
                    )
                }
            }

            const blockMinY = canvas.height - fontHeight
            // Motion done; display shafts graphically
            for (let shaftIndex = 0; shaftIndex < this.loomInfo.num_shafts; shaftIndex++) {
                let bitValue = bitmask & (1n << BigInt(shaftIndex))
                let blockHeight = bitValue == 0n ? ShaftLoweredHeight : ShaftRaisedHeight
                ctx.fillRect(
                    shaftIndex * blockAndSepWidth + firstBlockStartX,
                    blockMinY,
                    blockWidth,
                    -blockHeight,
                )
            }

        } else {
            // Display shaft state as a word
            let stateText = ShaftStateTranslationDict[this.shaftState.state]
            if (this.shaftState.state == ShaftStateEnum.ERROR) {
                ctx.fillStyle = "red"
            }
            ctx.textAlign = "left"
            ctx.fillText(
                stateText,
                0,
                Math.round(canvas.height / 2),
            )
        }

    }

    /*
    Display the status message (a combination of this.loomConnectionState and this.statusMessage)
    */
    displayStatusMessage() {
        let text = ConnectionStateTranslationDict[this.loomConnectionState.state]
        let textColor = null
        if (this.isConnected() && (this.statusMessage != null)) {
            text = this.statusMessage.message
            textColor = SeverityColors[this.statusMessage.severity]
        } else if (!this.isConnected()) {
            this.statusMessage = null
            textColor = "red"  // loom must be connected to weave
        }
        let statusElt = document.getElementById("status")
        statusElt.textContent = text
        statusElt.style.color = textColor
    }

    /*
    Display a portion of threading on the "threading_canvas" element.
     
    Center the jump or current range horizontally.
    */
    displayThreadingPattern() {
        if (this.mode != ModeEnum.THREADING) {
            return
        }

        let canvas = document.getElementById("threading_canvas")
        let ctx = canvas.getContext("2d")

        // Make resizing work better,
        // and, in the case of height, prevent the height growing with each new shed.
        canvas.width = 150
        canvas.height = 100

        ctx.clearRect(0, 0, canvas.width, canvas.height)

        let rect = document.getElementById("threading_canvas_container").getBoundingClientRect()
        canvas.width = asOddDecreased(rect.width)
        canvas.height = asOddDecreased(rect.height)

        if ((this.settings == null)
            || (this.separateThreadingRepeatsData.separate == null)
            || (this.currentEndData.end_number0 == null)
            || !this.currentPattern) {
            // Now that it's the right size, leave it blank
            return
        }
        const isDarkMode = window.matchMedia('(prefers-color-scheme: dark)')
        const fontColor = isDarkMode.matches ? "#ffffff" : "#000000"

        // Are we adding threads from lowToHigh?
        // Used to determine which threads are already threaded, and thus to make them darker.
        // This is not affected by threading/unthreading, unlike BaseLoomServer.thread_low_to_high.
        let lowToHigh = (this.settings.thread_back_to_front == this.settings.thread_right_to_left)
        if (!this.settings.end1_on_right) {
            lowToHigh = !lowToHigh
        }

        const isJump = this.jumpEndData.end_number0 != null
        const endData = isJump ? this.jumpEndData : this.currentEndData
        const endNumber0 = endData.end_number0
        const totalEndNumber0 = endData.total_end_number0
        const totalEndNumber1 = endData.total_end_number1
        const groupSize = totalEndNumber1 - totalEndNumber0 + 1
        const separateThreadingRepeats = this.separateThreadingRepeatsData.separate
        const centerX = ((canvas.width + 1) / 2)

        // Deal with fonts
        const endLabelElt = document.getElementById("end_label")
        ctx.font = window.getComputedStyle(endLabelElt).font
        // Set properties such that the position for fillText is the center of the text
        ctx.textBaseline = "middle"
        ctx.textAlign = "center"
        // Measure the space required for a shaft number (max 2 digits)
        const fontMeas = ctx.measureText("59")
        const fontHeight = Math.ceil(fontMeas.fontBoundingBoxAscent + fontMeas.fontBoundingBoxDescent)
        const blockWidth = asOddIncreased(fontMeas.width + ThreadingWidthGap)

        // Compute number of ends per end number (out how far apart to space the end numbers)
        // Display as many as one number per group, but no more than one every 4 ends
        // and leave enough space that we can display 4-digit end numbers plus a bit of gap
        // (thus measure the width of 5 digits instead of 4).
        const fourDigitWidth = ctx.measureText("9999").width
        const minEndsPerEndNumber = Math.ceil(fourDigitWidth / blockWidth)
        const numEndsPerEndNumber = Math.max(4, minEndsPerEndNumber)
        const displayEndNumberOffset = totalEndNumber0 % numEndsPerEndNumber

        let blockHeight = asOddIncreased(fontHeight)
        const numEnds = this.currentPattern.warp_colors.length
        const remainingHeight = canvas.height - (blockHeight + fontHeight) - ThreadingEndTopGap
        const verticalDelta = Math.floor(remainingHeight / this.loomInfo.num_shafts)

        let numEndsToShow = Math.round(canvas.width / blockWidth)
        // numEndsToShow and groupSize must both be odd or both be even;
        // otherwise the current group will not be centered.
        if ((groupSize % 2) != (numEndsToShow % 2)) {
            numEndsToShow -= 1
        }
        const leftBarCenterX = centerX - Math.ceil((numEndsToShow - 1) * blockWidth / 2)
        const rightBarCenterX = leftBarCenterX + ((numEndsToShow - 1) * blockWidth)

        const slotIndexGroupStart = (numEndsToShow - groupSize) / 2
        const slotIndexGroupEnd = slotIndexGroupStart + groupSize - 1

        // Display a box around the current group of ends.
        ctx.globalAlpha = isJump ? UnthreadedAlpha : 1.0
        const rectWidth = blockWidth * groupSize
        ctx.strokeRect(
            centerX - Math.round(rectWidth / 2),
            blockHeight + ThreadingEndTopGap,
            rectWidth,
            canvas.height - blockHeight - 2,
        )
        ctx.globalAlpha = 1.0

        // The following code relies on displaying ends in the order already-threaded to not-yet-threaded.
        // That simplifies the algorithm for leaving a gap between repeats in the not-yet-threaded ends.

        // Initialize totalEndNumber to the value just before the first end to show
        // (because the value is incremented at the beginning of the loop).
        let totalEndNumber = lowToHigh ? totalEndNumber0 - slotIndexGroupStart - 1 : totalEndNumber1 + slotIndexGroupStart + 1
        if (endNumber0 == 0) {
            if (lowToHigh) {
                // Offset to leave room for the gap in the middle.
                // I am not sure why this is needed.
                totalEndNumber += 1
            }
        }
        let endNumber = ((totalEndNumber - 1) % numEnds) + 1
        if (endNumber < 0) {
            endNumber += numEnds
        }
        let yShaftNumberBaseline = 0  // declare for later use
        const halfTopGap = Math.floor(ThreadingEndTopGap / 2)
        const firstAllowedNumberedSlotIndex = minEndsPerEndNumber - 1
        const lastAllowedNumberedSlotIndex = numEndsToShow - minEndsPerEndNumber
        for (let slotIndex = 0; slotIndex < numEndsToShow; slotIndex++) {
            if ((slotIndex == slotIndexGroupStart) && (endNumber0 == 0)) {
                // Display the group to be threaded as a gap.
                // Set endNumber appropriately for the next group of threads after this gap.
                endNumber = lowToHigh ? 0 : numEnds + 1
                continue
            }
            if (lowToHigh) {
                endNumber += 1
                if (endNumber > numEnds) {
                    if (separateThreadingRepeats & (slotIndex > slotIndexGroupEnd)) {
                        // Display a gap in the to-be-threaded area.
                        endNumber = 0
                        continue
                    }
                    // Do not display a gap; advance to the next end.
                    endNumber = 1
                }
                totalEndNumber += 1
            } else {
                endNumber -= 1
                if (endNumber < 1) {
                    // Display a gap in the to-be-threaded area.
                    if (separateThreadingRepeats && (slotIndex > slotIndexGroupEnd)) {
                        endNumber = numEnds + 1
                        continue
                    }
                    // Do not display a gap; advance to the next end.
                    endNumber = numEnds
                }
                totalEndNumber -= 1
            }
            if (totalEndNumber <= 0) {
                continue
            }

            let endIndex = endNumber - 1

            if (slotIndex < slotIndexGroupStart) {
                ctx.globalAlpha = ThreadedAlpha
            } else if (slotIndex > slotIndexGroupEnd) {
                ctx.globalAlpha = UnthreadedAlpha
            } else {
                ctx.globalAlpha = isJump ? UnthreadedAlpha : 1.0
            }

            const shaftIndex = this.currentPattern.threading[endIndex]
            const xBarCenter = this.settings.thread_right_to_left ? rightBarCenterX - (blockWidth * slotIndex) : leftBarCenterX + (blockWidth * slotIndex)
            if (this.settings.thread_back_to_front) {
                yShaftNumberBaseline = canvas.height - verticalDelta * (shaftIndex + 0.5) - fontMeas.fontBoundingBoxDescent
            } else {
                yShaftNumberBaseline = canvas.height - verticalDelta * (this.loomInfo.num_shafts - shaftIndex - 0.5) - fontMeas.fontBoundingBoxDescent
            }

            // Display total end number, if wanted, above this bar.
            if (((totalEndNumber - displayEndNumberOffset) % numEndsPerEndNumber == 0)
                && (slotIndex >= firstAllowedNumberedSlotIndex)
                && (slotIndex <= lastAllowedNumberedSlotIndex)) {
                ctx.fillStyle = fontColor
                ctx.fillText(
                    totalEndNumber,
                    xBarCenter,
                    fontMeas.fontBoundingBoxAscent + halfTopGap + 2,
                )
            }

            // Display weft end in three parts, in this order:
            // * A vertical colored bar with thread gradient below the shaft number,
            // * A similar vertical bar above the shaft number.
            // * The shaft number
            const xBarStart = xBarCenter - WeavingThreadHalfWidth
            const xBarEnd = xBarCenter + WeavingThreadHalfWidth
            const endColor = this.currentPattern.color_table[this.currentPattern.warp_colors[endIndex]]
            let endGradient = ctx.createLinearGradient(xBarStart, 0, xBarEnd, 0)
            endGradient.addColorStop(0, "lightgray")
            endGradient.addColorStop(0.2, endColor)
            endGradient.addColorStop(0.8, endColor)
            endGradient.addColorStop(1, "darkgray")
            ctx.fillStyle = endGradient
            ctx.fillRect(
                xBarCenter - WeavingThreadHalfWidth,
                blockHeight + ThreadingEndTopGap,
                WeavingThreadHalfWidth * 2,
                yShaftNumberBaseline - Math.round(blockHeight / 2) - blockHeight - 2 - ThreadingEndTopGap,
            )
            ctx.fillRect(
                xBarCenter - WeavingThreadHalfWidth,
                yShaftNumberBaseline + Math.round(blockHeight / 2) + halfTopGap,
                WeavingThreadHalfWidth * 2,
                canvas.height - (yShaftNumberBaseline + Math.round(blockHeight / 2) + 2)
            )
            ctx.fillStyle = fontColor
            ctx.fillText(
                shaftIndex + 1,
                xBarCenter,
                yShaftNumberBaseline,
            )
        }
    }

    /*
    Display weaving pattern on the "pattern_canvas" element.

    A no-op if not in WEAVING mode.
     
    Center the jump or current pick vertically.
    */
    displayWeavingPattern() {
        if (this.mode != ModeEnum.WEAVING) {
            return
        }

        const end1OnRight = this.settings.end1_on_right

        let pickColorCanvas = document.getElementById("pick_color")
        let canvas = document.getElementById("pattern_canvas")

        let ctx = canvas.getContext("2d")
        ctx.clearRect(0, 0, canvas.width, canvas.height)

        let pickColorCtx = pickColorCanvas.getContext("2d")
        pickColorCtx.clearRect(0, 0, pickColorCanvas.width, pickColorCanvas.height)

        // Make resizing work better,
        // and, in the case of height, prevent the height growing with each new shed.
        canvas.width = 150
        canvas.height = 100

        let rect = document.getElementById("pattern_canvas_container").getBoundingClientRect()
        canvas.width = asOddDecreased(rect.width)
        canvas.height = asOddDecreased(rect.height)

        if ((this.settings == null)
            || (this.separateWeavingRepeatsData.separate == null)
            || (this.currentPickData.pick_number == null)
            || !this.currentPattern) {
            // Now that it's the right size, leave it blank
            return
        }

        const separateRepeats = this.separateWeavingRepeatsData.separate
        const numEnds = this.currentPattern.warp_colors.length
        const numPicks = this.currentPattern.picks.length

        const isJump = this.jumpPickNumber.pick_number != null
        let centerTotalPickNumber = isJump ? this.jumpPickNumber.total_pick_number : this.currentPickData.total_pick_number
        const centerPickNumber = isJump ? this.jumpPickNumber.pick_number : this.currentPickData.pick_number

        if (centerPickNumber == null) {
            return
        }
        if (centerPickNumber == 0) {
            // We are at a gap
            centerTotalPickNumber += 1
        }

        if ((centerPickNumber > 0) && (centerPickNumber <= numPicks)) {
            const pick = this.currentPattern.picks[centerPickNumber - 1]
            let pickColorGradient = ctx.createLinearGradient(0, 0, 0, pickColorCanvas.height)
            let pickColor = this.currentPattern.color_table[pick.color]
            pickColorGradient.addColorStop(0, "lightgray")
            pickColorGradient.addColorStop(0.2, pickColor)
            pickColorGradient.addColorStop(0.8, pickColor)
            pickColorGradient.addColorStop(1, "darkgray")

            pickColorCtx.fillStyle = pickColorGradient
            pickColorCtx.fillRect(0, 0, pickColorCanvas.width, pickColorCanvas.height)
        }
        const blockSize = asOddDecreased(Math.min(
            Math.max(Math.round(canvas.width / numEnds), MinBlockSize),
            Math.max(Math.round(canvas.height / numPicks), MinBlockSize),
            MaxBlockSize))

        const numEndsToShow = Math.min(numEnds, Math.floor(canvas.width / blockSize))
        const numPicksToShow = asOddDecreased(Math.ceil(canvas.height / blockSize))

        let warpGradients = {}
        for (let i = 0; i < numEndsToShow; i++) {
            const threadColor = this.currentPattern.color_table[this.currentPattern.warp_colors[i]]
            const xStart = end1OnRight ? canvas.width - blockSize * (i + 1) : blockSize * i
            let warpGradient = ctx.createLinearGradient(xStart + WeavingThreadDisplayGap, 0, xStart + blockSize - (2 * WeavingThreadDisplayGap), 0)
            warpGradient.addColorStop(0, "lightgray")
            warpGradient.addColorStop(0.2, threadColor)
            warpGradient.addColorStop(0.8, threadColor)
            warpGradient.addColorStop(1, "darkgray")
            warpGradients[i] = warpGradient
        }

        let yOffset = Math.floor((canvas.height - (blockSize * numPicksToShow)) / 2)

        // Set initial totalPicknum and pickNum to 1 fewer than the first row to display,
        // then increment the values at the start of the display loop.
        let totalPickNumber = centerTotalPickNumber - ((numPicksToShow - 1) / 2) - 1
        let pickNumber = ((totalPickNumber - 1) % numPicks) + 1
        if (pickNumber < 0) {
            pickNumber += numPicks
        }

        const centerRowIndex = (numPicksToShow - 1) / 2
        const lastColoredRowIndex = isJump ? centerRowIndex - 1 : centerRowIndex

        for (let rowIndex = 0; rowIndex < numPicksToShow; rowIndex++) {
            if ((centerPickNumber == 0) && (rowIndex == centerRowIndex)) {
                // Display a gap for the current pick.
                pickNumber = 0
            } else if (separateRepeats && (rowIndex > centerRowIndex) && (pickNumber == numPicks)) {
                // Display a gap for this future pick.
                pickNumber = 0
            } else {
                totalPickNumber += 1
                pickNumber = (pickNumber % numPicks) + 1
            }
            if ((totalPickNumber <= 0) || (pickNumber == 0)) {
                continue
            }

            let pickIndex = pickNumber - 1

            if (rowIndex <= lastColoredRowIndex) {
                ctx.globalAlpha = 1.0
            } else {
                ctx.globalAlpha = 0.3
            }

            const yStart = canvas.height - (yOffset + (blockSize * (rowIndex + 1)))
            let pickGradient = ctx.createLinearGradient(0, yStart + WeavingThreadDisplayGap, 0, yStart + blockSize - (2 * WeavingThreadDisplayGap))
            const pickColor = this.currentPattern.color_table[this.currentPattern.picks[pickIndex].color]
            pickGradient.addColorStop(0, "lightgray")
            pickGradient.addColorStop(0.2, pickColor)
            pickGradient.addColorStop(0.8, pickColor)
            pickGradient.addColorStop(1, "gray")

            const shaft_word = this.currentPattern.picks[pickIndex].shaft_word
            for (let end = 0; end < numEndsToShow; end++) {
                const shaft = this.currentPattern.threading[end]
                const xStart = end1OnRight ? canvas.width - blockSize * (end + 1) : blockSize * end
                if (shaft_word & (1n << BigInt(shaft))) {
                    // Display warp end
                    ctx.fillStyle = warpGradients[end]
                    ctx.fillRect(
                        xStart + WeavingThreadDisplayGap,
                        yStart,
                        blockSize - (2 * WeavingThreadDisplayGap),
                        blockSize)
                } else {
                    // Display weft pick
                    ctx.fillStyle = pickGradient
                    ctx.fillRect(
                        xStart,
                        yStart + WeavingThreadDisplayGap,
                        blockSize,
                        blockSize - (2 * WeavingThreadDisplayGap))
                }
            }
        }

        ctx.globalAlpha = 1.0
        if (isJump) {
            // Jump pick: draw a dashed line around the (centered) jump pick,
            // and, if on the canvas, a solid line around the current pick
            ctx.setLineDash([1, 3])
            ctx.strokeRect(
                0,
                (canvas.height - blockSize) / 2,
                canvas.width,
                blockSize)
            ctx.setLineDash([])
            const currentPickOffset = this.currentPickData.total_pick_number - centerTotalPickNumber
            ctx.strokeRect(
                0,
                ((canvas.height - blockSize) / 2) - (blockSize * (currentPickOffset)),
                canvas.width,
                blockSize)
        } else {
            // No jump pick number; draw a solid line around the (centered) current pick
            ctx.setLineDash([])
            ctx.strokeRect(
                0,
                (canvas.height - blockSize) / 2,
                canvas.width,
                blockSize)
        }
    }

    /*
    Get the number of ends in the current pattern, or null if no current pattern 
    */
    getNumberOfEndsInPattern() {
        if (this.currentPattern) {
            return this.currentPattern.threading.length
        }
        return null
    }

    /*
    Get the number of picks in the current pattern, or null if no current pattern 
    */
    getNumberOfPicksInPattern() {
        if (this.currentPattern) {
            return this.currentPattern.picks.length
        }
        return null
    }

    /*
    Handle dark/light theme
    */
    handleDarkLightTheme() {
        const isDarkMode = window.matchMedia('(prefers-color-scheme: dark)')
        const themeValue = isDarkMode.matches ? 'dark' : 'light'
        document.documentElement.setAttribute('data-theme', themeValue)
        // The shaft state canvas needs to contrast with the background
        // and the color is not set by css, so...
        this.displayCanvases()
    }

    /*
    Process a reply from the loom server (data read from the web socket)
    */
    handleServerReply(event) {
        let messageElt = document.getElementById("read_message")
        if (event.data.length <= 80) {
            messageElt.textContent = event.data
        } else {
            messageElt.textContent = event.data.substring(0, 80) + "..."
        }
        let commandProblemElt = document.getElementById("command_problem")

        const datadict = JSON.parse(event.data)
        let resetCommandProblemMessage = true
        if (datadict.type == "CommandDone") {
            if (datadict.success) {
                if (this.statusMessage != null) {
                    this.statusMessage = null
                    this.displayStatusMessage()
                }
            } else {
                resetCommandProblemMessage = false
                commandProblemElt.textContent = truncateStr(datadict.message)
                commandProblemElt.style.color = SeverityColors[SeverityEnum.ERROR]
            }
            let cmdFuture = this.commandFutures[datadict.cmd_type]
            if ((cmdFuture != null) && (!cmdFuture.done)) {
                cmdFuture.setResult(datadict)
            }
        } else if (datadict.type == "CommandProblem") {
            resetCommandProblemMessage = false
            let color = SeverityColors[datadict.severity]
            if (color == null) {
                color = "#ffffff"
            }
            commandProblemElt.textContent = truncateStr(datadict.message)
            commandProblemElt.style.color = color
        } else if (datadict.type == "CurrentEndNumber") {
            if (!this.currentPattern) {
                console.log("Ignoring CurrentEndNumber: no pattern loaded")
            }
            this.currentEndData = datadict
            this.currentPattern.end_number0 = datadict.end_number0
            this.currentPattern.end_number1 = datadict.end_number1
            this.currentPattern.end_repeat_number = datadict.end_repeat_number
            this.displayThreadingPattern()
            this.displayEnds()
        } else if (datadict.type == "CurrentPickNumber") {
            if (!this.currentPattern) {
                this.currentPickData = NullPickData
                console.log("Ignoring CurrentPickNumber: no pattern loaded")
            }
            this.currentPickData = datadict
            this.displayWeavingPattern()
            this.displayPick()
        } else if (datadict.type == "JumpEndNumber") {
            this.jumpEndData = datadict
            this.displayJumpEnd()
        } else if (datadict.type == "JumpPickNumber") {
            this.jumpPickNumber = datadict
            this.displayJumpPick()
        } else if (datadict.type == "LanguageNames") {
            this.displayLanguageNames(datadict.languages)
        } else if (datadict.type == "LoomConnectionState") {
            this.loomConnectionState = datadict
            this.displayStatusMessage()
        } else if (datadict.type == "LoomInfo") {
            this.loomInfo = datadict
            this.displayLoomInfo()
        } else if (datadict.type == "Mode") {
            this.mode = datadict.mode
            this.displayMode()
        } else if (datadict.type == "PatternNames") {
            /*
            Why this code is so odd:
            * The <hr> separator is not part of option list, and there is no good way
              to add a separator in javascript, so I preserve the old one.
            * The obvious solution is to remove the old names, then insert new ones.
              Unfortunately that loses the <hr> separator.
            * So I insert the new names, then remove the old ones. Ugly, but at least
              on macOS Safari 18.1.1 this preserves the separator. If the separator
              is lost on other systems, the menu is still usable.
     
            Also there is subtlety in the case that there is no current weavingPattern
            (in which case the menu should be shown as blank).
            I wanted to avoid the hassle of adding a blank option now,
            which would then have to be purged on the next call to select_pattern.
            Fortunately not bothring to add a blank entry works perfectly!
            At the end the menu value is set to "", which shows as blank,
            and there is no blank option that has to be purged later.
            */
            let patternMenu = document.getElementById("pattern_menu")
            let patternNames = datadict.names
            let menuOptions = patternMenu.options
            let currentName = this.currentPattern ? this.currentPattern.name : ""

            // This preserves the separator if called with no names
            if (patternNames.length == 0) {
                patternNames.push("")
            }

            // Save this value for later deletion of old pattern names
            let numOldPatternNames = patternMenu.options.length - 1

            // Insert new pattern names
            for (let patternName of patternNames) {
                let option = new Option(patternName)
                menuOptions.add(option, 0)
            }

            // Purge old pattern names
            for (let i = 0; i < numOldPatternNames; i++) {
                menuOptions.remove(patternNames.length)
            }
            patternMenu.value = currentName
        } else if (datadict.type == "ReducedPattern") {
            this.currentPattern = new ReducedPattern(datadict)
            this.currentEndData = NullEndData
            this.currentPickData = NullPickData
            this.jumpEndData = NullEndData
            this.jumpPickData = NullPickData
            let patternMenu = document.getElementById("pattern_menu")
            patternMenu.value = this.currentPattern.name
            this.displayCanvases()
        } else if (datadict.type == "SeparateThreadingRepeats") {
            this.separateThreadingRepeatsData = datadict
            let separateThreadingRepeatsCheckbox = document.getElementById("separate_threading_repeats")
            separateThreadingRepeatsCheckbox.checked = datadict.separate
            this.displayThreadingPattern()
        } else if (datadict.type == "SeparateWeavingRepeats") {
            this.separateWeavingRepeatsData = datadict
            let separateWeavingRepeatsCheckbox = document.getElementById("separate_weaving_repeats")
            separateWeavingRepeatsCheckbox.checked = datadict.separate
            this.displayWeavingPattern()
        } else if (datadict.type == "Settings") {
            this.settings = datadict
            this.displaySettings()
        } else if (datadict.type == "ShaftState") {
            this.shaftState = datadict
            this.displayShaftState()
        } else if (datadict.type == "StatusMessage") {
            resetCommandProblemMessage = false
            this.statusMessage = datadict
            this.displayStatusMessage()
        } else if (datadict.type == "Direction") {
            this.direction = datadict
            this.displayDirection()
        } else if (datadict.type == "ThreadGroupSize") {
            this.threadGroupSize = datadict.group_size
            let threadGroupSizeMenu = document.getElementById("thread_group_size")
            threadGroupSizeMenu.value = this.threadGroupSize
        } else {
            console.warn(`Unknown message type ${datadict.type}`, datadict)
        }
        if (resetCommandProblemMessage) {
            commandProblemElt.textContent = ""
            commandProblemElt.style.color = "#ffffff"
        }
    }

    /*
    Handle the pattern_menu select menu.
    
    Send the "select_pattern" or "clear_pattern_names" command.
    */
    async handlePatternMenu(event) {
        let patternMenu = document.getElementById("pattern_menu")
        let command
        if (patternMenu.value == "Clear Recents") {
            command = { "type": "clear_pattern_names" }
        } else {
            command = { "type": "select_pattern", "name": patternMenu.value }
        }
        await this.sendCommand(command)
    }

    /*
    Handle user editing of jump_end_number.
    */
    async handleJumpToEndInput(event) {
        let jumpToEndSubmitElt = document.getElementById("jump_to_end_submit")
        let jumpToEndResetElt = document.getElementById("jump_to_end_reset")
        let jumpTotalEndNumber0Elt = document.getElementById("jump_total_end_number0")
        jumpTotalEndNumber0Elt.value = jumpTotalEndNumber0Elt.value.replace(/\D/g, "")
        let disableJump = (asIntOrNull(jumpTotalEndNumber0Elt.value) == this.jumpEndData.total_end_number0)
        jumpTotalEndNumber0Elt.setAttribute('modified', !disableJump)
        const disableReset = disableJump && (jumpTotalEndNumber0Elt.value == "")
        jumpToEndSubmitElt.disabled = disableJump
        jumpToEndResetElt.disabled = disableReset
        if (event != null) {
            event.preventDefault()
        }
    }

    /*
    Handle Reset buttin in the "jump_to_end" form.
    
    Reset end number and repeat number to current values.
    */
    async handleJumpToEndReset(event) {
        const jumpTotalEndNumber0Elt = document.getElementById("jump_total_end_number0")
        jumpTotalEndNumber0Elt.value = ""
        const command = { "type": "jump_to_end", "total_end_number0": null }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle jump_to_end form submit.
    
    Send the "jump_to_end" command.
    */
    async handleJumpToEndSubmit(event) {
        const jumpTotalEndNumber0Elt = document.getElementById("jump_total_end_number0")
        const totalEndNumber0 = asIntOrNull(jumpTotalEndNumber0Elt.value)
        const command = { "type": "jump_to_end", "total_end_number0": totalEndNumber0 }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle user editing of jump_total_pick_number.
    */
    async handleJumpToPickInput(event) {
        let jumpToPickSubmitElt = document.getElementById("jump_to_pick_submit")
        let jumpToPickResetElt = document.getElementById("jump_to_pick_reset")
        let jumpTotalPickNumberElt = document.getElementById("jump_total_pick_number")

        jumpTotalPickNumberElt.value = jumpTotalPickNumberElt.value.replace(/\D/g, "")
        const disableJump = asIntOrNull(jumpTotalPickNumberElt.value) == this.jumpPickNumber.total_pick_number
        jumpTotalPickNumberElt.setAttribute('modified', !disableJump)
        const disableReset = disableJump && (jumpTotalPickNumberElt.value == "")
        jumpToPickSubmitElt.disabled = disableJump
        jumpToPickResetElt.disabled = disableReset
        if (event != null) {
            event.preventDefault()
        }
    }

    /*
    Handle Reset buttin in the "jump_to_pick" form.
    
    Reset pick number and repeat number to current values.
    */
    async handleJumpToPickReset(event) {
        const jumpTotalPickNumberElt = document.getElementById("jump_total_pick_number")
        jumpTotalPickNumberElt.value = ""
        const command = { "type": "jump_to_pick", "total_pick_number": null }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle jump_to_pick form submit.
    
    Send the "jump_to_pick" command.
    */
    async handleJumpToPickSubmit(event) {
        const jumpTotalPickNumberElt = document.getElementById("jump_total_pick_number")
        const jumpTotalPickNumber = asIntOrNull(jumpTotalPickNumberElt.value)
        const command = { "type": "jump_to_pick", "total_pick_number": jumpTotalPickNumber }
        await this.sendCommand(command)
        jumpTotalPickNumberElt.select()
        event.preventDefault()
    }

    /*
    Handle typing in loom name input
    */
    async handleLoomNameInput(event) {
        let disableSubmit = true
        let loomNameInputElt = document.getElementById("setting_loom_name_input")
        let loomNameSubmitButton = document.getElementById("setting_loom_name_submit")
        let loomNameResetButton = document.getElementById("setting_loom_name_reset")
        if (loomNameInputElt.value != this.settings.loom_name) {
            loomNameInputElt.style.backgroundColor = "pink"
            disableSubmit = false
        } else {
            loomNameInputElt.style.backgroundColor = "white"
        }
        loomNameSubmitButton.disabled = disableSubmit
        loomNameResetButton.disabled = disableSubmit
        if (event != null) {
            event.preventDefault()
        }
    }

    /*
    Handle the mode tab bar buttons

    Mode us a ModeEnum value
    */
    async handleMode(mode, event) {
        const command = { "type": "mode", "mode": mode }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle the debug change direction button.
    
    Send "oobcommand" command "d".
    */
    async handleDebugChangeDirection(event) {
        let command = { "type": "oobcommand", "command": "d" }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle the debug close connection button.
    
    Send "oobcommand" command "c".
    */
    async handleDebugCloseConnection(event) {
        let command = { "type": "oobcommand", "command": "c" }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle the debug Hide button by hiding the debug controls
    */
    async handleDebugHide(event) {
        let debugDivElt = document.getElementById("debug_div")
        debugDivElt.style.display = "none"
        this.displayCanvases()
    }

    /*
    Handle the debug next pick button.
    
    Send "oobcommand" command "n".
    */
    async handleDebugNextPick(event) {
        let command = { "type": "oobcommand", "command": "n" }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle a "Separate repeats" checkbox
    */
    async handleSeparateRepeats(isThreading, event) {
        const name = isThreading ? "threading" : "weaving"
        const command = { "type": `separate_${name}_repeats`, "separate": event.target.checked }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle settings form reset
    */
    async handleSettingsReset(event) {
        this.displaySettings()
    }

    /*
    Handle the thread group size select menu
    */
    async handleThreadGroupSize(event) {
        const threadGroupSizeElt = document.getElementById("thread_group_size")
        const command = { "type": "thread_group_size", "group_size": asIntOrNull(threadGroupSizeElt.value) }
        await this.sendCommand(command)
    }

    /*
    Handle weaving and threading direction button clicks.
    
    Send the direction command to the loom server.
    */
    async handleToggleDirection(event) {
        let command = { "type": "direction", "forward": !this.direction.forward }
        await this.sendCommand(command)
    }

    async handleUploadButton(event) {
        let uploadFileInputElt = document.getElementById("upload_file_input")
        uploadFileInputElt.click()
        if (event != null) {
            event.preventDefault()
        }
    }

    /*
    Handle pattern files dropped on upload drop area
    */
    async handleUploadDrop(event) {
        await this.uploadFiles(event.dataTransfer.files)
        if (event != null) {
            event.preventDefault()
        }
    }

    /*
    Handle pattern files from the hidden upload_file_input element
    */
    async handleUploadFileInput(event) {
        await this.uploadFiles(event.target.files)
        // Reset file list so one can upload the same file again
        event.target.value = ""
        if (event != null) {
            event.preventDefault()
        }
    }

    isConnected() {
        return this.loomConnectionState.state == ConnectionStateEnum.CONNECTED
    }

    /*
    * Select the text in an input field when it gets focus
    *
    * Use as follows:
    *   myInputElt.addEventListener("focus", this.selectOnInput.bind(this, myInputElt))
    *
    * See https://stackoverflow.com/a/13542708/1653413 for why the obvious solution fails.
    */
    selectOnInput(inputField) {
        setTimeout(function () { inputField.select() }, 0)
    }

    /*
    Send a command to the loom server.
    */
    async sendCommand(commandDict) {
        let commandElt = document.getElementById("sent_command")
        let commandStr = JSON.stringify(commandDict)
        if (commandStr.length <= 80) {
            commandElt.textContent = commandStr
        } else {
            commandElt.textContent = commandStr.substring(0, 80) + "..."
        }
        await this.ws.send(commandStr)
    }

    /*
    Send a command to the loom server and wait for the command to finish.

    Return the CommandDone reply dict.
    */
    async sendCommandAndWait(commandDict, timeoutMs = 5000) {
        let oldFuture = this.commandFutures[commandDict.type]
        if ((oldFuture != null) && (!oldFuture.done)) {
            oldFuture.setException(Error("superseded"))
        }
        let newFuture = new Future(commandDict.type, timeoutMs)
        this.commandFutures[commandDict.type] = newFuture
        await this.sendCommand(commandDict)
        return newFuture
    }

    /*
    Handle settings form submit
    */
    async sendSettings(event) {
        let loomNameInputElt = document.getElementById("setting_loom_name_input")
        let settingLanguageElt = document.getElementById("setting_language")
        let directionControlElt = document.getElementById("setting_direction_control")
        let end1OnRightElt = document.getElementById("setting_end1_on_right")
        let threadRightToLeftElt = document.getElementById("setting_thread_right_to_left")
        let threadBackToFrontElt = document.getElementById("setting_thread_back_to_front")
        let defaultThreadGroupSize = document.getElementById("setting_thread_group_size")
        const languageChanged = settingLanguageElt.value != this.settings.language
        const command = {
            "type": "settings",
            "language": settingLanguageElt.value,
            "loom_name": loomNameInputElt.value,
            "direction_control": asIntOrNull(directionControlElt.value),
            "end1_on_right": asBooleanOrNull(end1OnRightElt.value),
            "thread_right_to_left": asBooleanOrNull(threadRightToLeftElt.value),
            "thread_back_to_front": asBooleanOrNull(threadBackToFrontElt.value),
            "thread_group_size": asIntOrNull(defaultThreadGroupSize.value),
        }
        let replyDict = await this.sendCommandAndWait(command)
        if (replyDict.success && languageChanged) {
            window.location.reload()
        }
        event.preventDefault()
    }

    /*
    Set the background color of an element.
     
    Intended for use as a callback, e.g. for drag-and-drop.
    */
    setBackgroundColor(element, color) {
        element.style.backgroundColor = color
    }

    /*
    Upload one or more files and select the first one.
    
    Send the "upload" and "select_pattern" commands.
    */
    async uploadFiles(fileList) {
        let commandProblemElt = document.getElementById("command_problem")
        if (fileList.length > MaxFiles) {
            commandProblemElt.textContent = t("Too many files") + `: ${fileList.length} > ${MaxFiles}`
            commandProblemElt.style.color = SeverityColors[SeverityEnum.ERROR]
            return
        }
        if (fileList.length == 0) {
            return
        }
        try {

            // Sort the file names; this requires a bit of extra work
            // because FileList doesn't support sort.

            let fileArray = Array.from(fileList)
            fileArray.sort(compareFiles)

            let isFirst = true
            for (let file of fileArray) {
                const fileExt = file.name.slice((file.name.lastIndexOf(".") - 1 >>> 0) + 2)
                // .wpo WeavePoint files are binary. Decode them as latin-1 strings
                // so that the data can reliably be encoded at the other end
                // (latin-1 encodes any possible byte to a corresponding 8-bit char).
                // All other files are text; assume utf-8.
                let data
                if (fileExt == "wpo") {
                    data = await readAndEncodeBinaryFile(file)
                } else {
                    data = await readTextFile(file, "utf-8")
                }
                const fileCommand = { "type": "upload", "name": file.name, "data": data }
                let replyDict = await this.sendCommandAndWait(fileCommand)
                if (!replyDict.success) {
                    return
                }
                if (isFirst) {
                    isFirst = false
                    const selectPatternCommand = { "type": "select_pattern", "name": file.name }
                    replyDict = await this.sendCommandAndWait(selectPatternCommand)
                    if (!replyDict.success) {
                        return
                    }
                }
            }
        } catch (error) {
            commandProblemElt.textContent = truncateStr(datadict.message)
            commandProblemElt.style.color = SeverityColors[SeverityEnum.ERROR]
        }
    }
}

loomClient = new LoomClient()
loomClient.init()
