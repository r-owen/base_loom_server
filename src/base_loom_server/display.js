// value is replaced by python code
const TranslationDict = { translation_dict }

// value is replaced by python code
const EnableSoftwareWeaveDirection = { enable_software_weave_direction }
console.log(`EnableSoftwareWeaveDirection=${EnableSoftwareWeaveDirection}`)

const MaxFiles = 10

const MinBlockSize = 11
const MaxBlockSize = 41

// Display gap on left and right edges end numbers
const EndDisplayGap = 3

// Display gap on left and right edges of warp and top and bottom edges of weft
const ThreadDisplayGap = 1

const ThreadHalfWidth = 5

const EndFont = "18px Times New Roman"

// Keys are the possible values of the LoomConnectionState.state messages
// Values are entries in ConnectionStateEnum
const ConnectionStateTranslationDict = {
    0: "disconnected",
    1: "connected",
    2: "connecting",
    3: "disconnecting",
}

const ModeEnum = {
    "WEAVING": 1,
    "THREADING": 2,
}

const SeverityColors = {
    1: "#ffffff",
    2: "yellow",
    3: "red",
}

const SeverityEnum = {
    "INFO": 1,
    "WARNING": 2,
    "ERROR": 3,
}

const ShaftStateTranslationDict = {
    0: "?",
    1: "done",
    2: "moving",
    3: "error",
}

let ConnectionStateEnum = {}
for (let key of Object.keys(ConnectionStateTranslationDict)) {
    let name = ConnectionStateTranslationDict[key]
    ConnectionStateEnum[name] = name
}
Object.freeze(ConnectionStateEnum)

const numericCollator = new Intl.Collator(undefined, { numeric: true })

/* Translate a phrase using TranslationDict */
function t(phrase) {
    if (!(phrase in TranslationDict)) {
        console.log(`Missing translation key: "${phrase}"`)
        return phrase
    }
    return TranslationDict[phrase]
}

class TimeoutError extends Error {
    constructor(message) {
        super(message)
        this.name = "TimeoutError"
    }
}

/* Return the largest odd integer <= value

The description isn't quite right for negative values;
those are first truncated towards 0, then made more negative if needed.
*/
function asOdd(value) {
    let ret = Math.trunc(value)
    return ret % 2 == 0 ? ret - 1 : ret
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

Parameters
----------
datadict : dict object
    Data from a Python ReducedPattern dataclass.
*/
class ReducedPattern {
    constructor(datadict) {
        this.name = datadict.name
        this.color_table = datadict.color_table
        this.warp_colors = datadict.warp_colors
        this.threading = datadict.threading
        this.picks = []
        this.pick_number = datadict.pick_number
        this.pick_repeat_number = datadict.pick_repeat_number
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


/*
Compare the names of two Files, taking numbers into account.

To sort file names in a FileList you must first 
convert the FileList to an Array::

    // myFileList is a FileList (which cannot be sorted)
    fileArr = Array.from(myFileList)
    fileArr.sort(compareFiles)
*/
function compareFiles(a, b) {
    // 
    return numericCollator.compare(a.name, b.name)
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
This version does not work, because "this" is the wrong thing in callbacks.
But it could probably be easily made to work by adding a
"addEventListener method that takes an id, an event name, and a function
and uses "bind" in the appropriate fashion.

The result might be a nice -- each assignment would be a single line.
*/

class LoomClient {
    constructor() {
        this.ws = new WebSocket("ws")
        // Dict of command type: Future for commands that were run with sendCommandAndWait
        this.commandFutures = {}
        this.currentPattern = null
        this.weaveForward = true
        this.loomConnectionState = ConnectionStateEnum.disconnected
        this.loomConnectionStateReason = ""
        this.statusMessage = null
        this.jumpPickNumber = null
        this.jumpPickRepeatNumber = null
        this.threadGroupSize = 4
        this.threadLowToHigh = true
        this.loomInfo = null

        // this.init()
    }

    init() {
        this.ws.onmessage = this.handleServerReply.bind(this)
        this.ws.onclose = handleWebsocketClosed

        // Assign event handlers for file drag-and-drop
        const dropAreaElt = document.body;

        ["dragenter", "dragover", "dragleave", "drop"].forEach(eventName => {
            dropAreaElt.addEventListener(eventName, preventDefaults)
        });

        ["dragenter", "dragover"].forEach(eventName => {
            dropAreaElt.addEventListener(eventName, highlight)
        });

        ["dragleave", "drop"].forEach(eventName => {
            dropAreaElt.addEventListener(eventName, unhighlight)
        })

        function highlight(event) {
            dropAreaElt.style.backgroundColor = "#E6E6FA"
        }

        function unhighlight(event) {
            dropAreaElt.style.backgroundColor = "#FFFFFF"
        }

        dropAreaElt.addEventListener("drop", this.handleDrop.bind(this))

        let tabWeavingElt = document.getElementById("mode_weaving")
        tabWeavingElt.addEventListener("click", this.handleMode.bind(this, ModeEnum.WEAVING))

        let tabThreadingElt = document.getElementById("mode_threading")
        tabThreadingElt.addEventListener("click", this.handleMode.bind(this, ModeEnum.THREADING))

        let fileInputElt = document.getElementById("file_input")
        fileInputElt.addEventListener("change", this.handleFileInput.bind(this))

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

        let jumpEndNumber0Elt = document.getElementById("jump_end_number0")
        // Select all text on focus, to make it easier to try different jump values
        // (without this, you are likely to append digits, which is rarely what you want)
        jumpEndNumber0Elt.addEventListener(`focus`, () => jumpEndNumber0Elt.select())
        jumpEndNumber0Elt.addEventListener("input", this.handleJumpToEndInput.bind(this))

        let jumpEndRepeatNumberElt = document.getElementById("jump_end_repeat_number")
        jumpEndRepeatNumberElt.addEventListener(`focus`, () => jumpEndRepeatNumberElt.select())
        jumpEndRepeatNumberElt.addEventListener("input", this.handleJumpToEndInput.bind(this))

        let jumpPickNumberElt = document.getElementById("jump_pick_number")
        jumpPickNumberElt.addEventListener(`focus`, () => jumpPickNumberElt.select())
        jumpPickNumberElt.addEventListener("input", this.handleJumpToPickInput.bind(this))

        let jumpPickRepeatNumberElt = document.getElementById("jump_pick_repeat_number")
        jumpPickRepeatNumberElt.addEventListener(`focus`, () => jumpPickRepeatNumberElt.select())
        jumpPickRepeatNumberElt.addEventListener("input", this.handleJumpToPickInput.bind(this))

        let oobChangeDirectionButton = document.getElementById("oob_change_direction")
        oobChangeDirectionButton.addEventListener("click", this.handleOOBChangeDirection.bind(this))

        let oobCloseConnectionButton = document.getElementById("oob_close_connection")
        oobCloseConnectionButton.addEventListener("click", this.handleOOBCloseConnection.bind(this))

        let oobNextPickButton = document.getElementById("oob_next_pick")
        oobNextPickButton.addEventListener("click", this.handleOOBNextPick.bind(this))

        let separateThreadingRepeatsCheckbox = document.getElementById("separate_threading_repeats")
        separateThreadingRepeatsCheckbox.addEventListener("change", this.handleSeparateRepeats.bind(this, true))

        let separateWeavingRepeatsCheckbox = document.getElementById("separate_weaving_repeats")
        separateWeavingRepeatsCheckbox.addEventListener("change", this.handleSeparateRepeats.bind(this, false))

        let threadDirectionElt = document.getElementById("thread_direction")
        threadDirectionElt.addEventListener("click", this.handleToggleThreadDirection.bind(this))

        let weaveDirectionElt = document.getElementById("weave_direction")
        if (EnableSoftwareWeaveDirection) {
            weaveDirectionElt.addEventListener("click", this.handleToggleWeaveDirection.bind(this))
        } else {
            weaveDirectionElt.disabled = true
        }
        let patternMenu = document.getElementById("pattern_menu")
        patternMenu.addEventListener("change", this.handlePatternMenu.bind(this))

        addEventListener("resize", (this.displayThreadingOrWeavingPattern.bind(this)))
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
            if (!datadict.success) {
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
            console.log("CommandProblem")
            commandProblemElt.textContent = truncateStr(datadict.message)
            commandProblemElt.style.color = color
        } else if (datadict.type == "CurrentEndNumber") {
            if (!this.currentPattern) {
                console.log("Ignoring CurrentEndNumber: no pattern loaded")
            }
            this.currentPattern.end_number0 = datadict.end_number0
            this.currentPattern.end_number1 = datadict.end_number1
            this.currentPattern.end_repeat_number = datadict.end_repeat_number
            this.displayThreadingPattern()
            this.displayEnds()
        } else if (datadict.type == "CurrentPickNumber") {
            if (!this.currentPattern) {
                console.log("Ignoring CurrentPickNumber: no pattern loaded")
            }
            this.currentPattern.pick_number = datadict.pick_number
            this.currentPattern.pick_repeat_number = datadict.pick_repeat_number
            this.displayWeavingPattern()
            this.displayPick()
        } else if (datadict.type == "JumpEndNumber") {
            this.jumpEndNumber0 = datadict.end_number0
            this.jumpEndNumber1 = datadict.end_number1
            this.jumpEndRepeatNumber = datadict.repeatNumber
            this.displayJumpEnd()
        } else if (datadict.type == "JumpPickNumber") {
            this.jumpPickNumber = datadict.pick_number
            this.jumpPickRepeatNumber = datadict.pick_repeat_number
            this.displayJumpPick()
        } else if (datadict.type == "LoomConnectionState") {
            this.loomConnectionState = datadict
            this.loomConnectionState.state = ConnectionStateTranslationDict[datadict.state]
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
            this.displayWeavingPattern()
            this.displayThreadingPattern()
            let patternMenu = document.getElementById("pattern_menu")
            patternMenu.value = this.currentPattern.name
        } else if (datadict.type == "SeparateThreadingRepeats") {
            let separateThreadingRepeatsCheckbox = document.getElementById("separate_threading_repeats")
            separateThreadingRepeatsCheckbox.checked = datadict.separate
        } else if (datadict.type == "SeparateWeavingRepeats") {
            let separateWeavingRepeatsCheckbox = document.getElementById("separate_weaving_repeats")
            separateWeavingRepeatsCheckbox.checked = datadict.separate
        } else if (datadict.type == "ShaftState") {
            this.displayShaftState(datadict)
        } else if (datadict.type == "StatusMessage") {
            resetCommandProblemMessage = false
            this.statusMessage = datadict
            this.displayStatusMessage()
        } else if (datadict.type == "ThreadDirection") {
            this.threadLowToHigh = datadict.low_to_high
            this.displayThreadingPattern()
            this.displayThreadDirection()
        } else if (datadict.type == "ThreadGroupSize") {
            this.threadGroupSize = datadict.group_size
            let threadGroupSizeMenu = document.getElementById("thread_group_size")
            threadGroupSizeMenu.value = this.threadGroupSize
        } else if (datadict.type == "WeaveDirection") {
            this.weaveForward = datadict.forward
            this.displayWeaveDirection()
        } else {
            console.log(`Unknown message type ${datadict.type}`, datadict)
        }
        if (resetCommandProblemMessage) {
            commandProblemElt.textContent = ""
            commandProblemElt.style.color = "#ffffff"
        }
    }

    isConnected() {
        return this.loomConnectionState.state == ConnectionStateEnum.connected
    }

    /*
    Display ShaftState
    */
    displayShaftState(datadict) {
        let text = ""
        let textColor = "black"
        if (datadict.state == 1) {
            // Move is done; display shaft numbers
            let raisedShaftList = []
            let bitmask = BigInt(datadict.shaft_word)
            let shaft_number = 1

            while (bitmask !== 0n) {
                if (bitmask & 1n) {
                    raisedShaftList.push(shaft_number)
                }
                bitmask >>= 1n
                shaft_number++
            }
            text = raisedShaftList.join(" ")
        } else {
            text = t(ShaftStateTranslationDict[datadict.state])
            if (datadict.state == 3) {
                textColor = "red"
            }
        }
        let shaftStateElt = document.getElementById("shaft_state")
        shaftStateElt.textContent = text
        shaftStateElt.style.color = textColor
    }

    /*
    Display the status message (a combination of self.loomConnectionState and self.statusMessage)
    */
    displayStatusMessage() {
        let text = t(this.loomConnectionState.state)
        let textColor = "black"
        if (this.isConnected() && (this.statusMessage != null)) {
            text = this.statusMessage.message
            textColor = SeverityColors[datadict.severity]
        } else if (!this.isConnected()) {
            this.statusMessage = null
            textColor = "red"  // loom must be connected to weave
        }
        let statusElt = document.getElementById("status")
        statusElt.textContent = text
        statusElt.style.color = textColor
    }

    /*
    Display the current end numbers.
    */
    displayEnds() {
        let endNumber0Elt = document.getElementById("end_number0")
        let endNumber1Elt = document.getElementById("end_number1")
        let repeatNumberElt = document.getElementById("end_repeat_number")
        let totalEndsElt = document.getElementById("total_ends")
        let endNumber0 = ""
        let endNumber1 = ""
        let totalEnds = "?"
        let repeatNumber = ""
        if (this.currentPattern) {
            endNumber0 = this.currentPattern.end_number0
            endNumber1 = this.currentPattern.end_number1
            repeatNumber = this.currentPattern.end_repeat_number
            totalEnds = this.currentPattern.threading.length
        }
        endNumber0Elt.textContent = endNumber0
        endNumber1Elt.textContent = endNumber1
        repeatNumberElt.textContent = repeatNumber
        totalEndsElt.textContent = totalEnds
    }

    /*
    Display the current pick and repeat.
    */
    displayPick() {
        let repeatNumberElt = document.getElementById("pick_repeat_number")
        let pickNumberElt = document.getElementById("pick_number")
        let totalPicksElt = document.getElementById("total_picks")
        let pickNumber = ""
        let totalPicks = "?"
        let repeatNumber = ""
        if (this.currentPattern) {
            pickNumber = this.currentPattern.pick_number
            repeatNumber = this.currentPattern.pick_repeat_number
            totalPicks = this.currentPattern.picks.length
        }
        pickNumberElt.textContent = pickNumber
        repeatNumberElt.textContent = repeatNumber
        totalPicksElt.textContent = totalPicks
    }

    /*
    Display the jump end and repeat
    */
    displayJumpEnd() {
        let endNumber0Elt = document.getElementById("jump_end_number0")
        let repeatNumberElt = document.getElementById("jump_end_repeat_number")
        if (!this.currentPattern) {
            this.jumpEndNumber0 = null
            this.jumpEndRepeatNumber = null
        }
        endNumber0Elt.value = nullToBlank(this.jumpEndNumber)
        repeatNumberElt.value = nullToBlank(this.jumpEndRepeatNumber)
        if (this.currentPattern) {
            this.displayThreadingPattern()
        }
        this.handleJumpToEndInput(null)
    }

    /*
    Display the jump pick and repeat
    */
    displayJumpPick() {
        let pickNumberElt = document.getElementById("jump_pick_number")
        let repeatNumberElt = document.getElementById("jump_pick_repeat_number")
        if (!this.currentPattern) {
            this.jumpPickNumber = null
            this.jumpPickRepeatNumber = null
        }
        pickNumberElt.value = nullToBlank(this.jumpPickNumber)
        repeatNumberElt.value = nullToBlank(this.jumpPickRepeatNumber)
        if (this.currentPattern) {
            this.displayWeavingPattern()
        }
        this.handleJumpToPickInput(null)
    }

    /*
    Display the current mode
    */
    displayMode() {
        // Get all elements with class="tablinks" and remove the class "active"
        let buttons = document.getElementsByClassName("tabchoices")
        for (let button of buttons) {
            button.className = button.className.replace(" active", "")
        }

        let elt = null
        let modeButton = null
        if (this.mode == ModeEnum.THREADING) {
            modeButton = document.getElementById("mode_threading")
            for (const elt of document.getElementsByClassName("weaving-flex")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("weaving-grid")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("threading-flex")) {
                elt.style.display = "flex"
            }
            for (const elt of document.getElementsByClassName("threading-grid")) {
                elt.style.display = "grid"
            }
            this.displayThreadingPattern()
        } else {
            // weaving
            modeButton = document.getElementById("mode_weaving")
            for (const elt of document.getElementsByClassName("threading-flex")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("threading-grid")) {
                elt.style.display = "none"
            }
            for (const elt of document.getElementsByClassName("weaving-flex")) {
                elt.style.display = "flex"
            }
            for (const elt of document.getElementsByClassName("weaving-grid")) {
                elt.style.display = "grid"
            }
            this.displayWeavingPattern()
        }
        if (modeButton != null) {
            modeButton.className += " active"
        }
    }

    displayThreadingOrWeavingPattern(event) {
        if (this.mode == ModeEnum.THREADING) {
            this.displayThreadingPattern(event)
        } else {
            this.displayWeavingPattern(event)
        }
    }

    /*
    Display thread direction
    */
    displayThreadDirection() {
        let threadDirectionElt = document.getElementById("thread_direction")
        if (this.threadLowToHigh) {
            threadDirectionElt.textContent = "←"
        } else {
            threadDirectionElt.textContent = "→"
        }
    }

    /*
    Display a portion of threading on the "threading_canvas" element.
     
    Center the jump or current range horizontally.
    */
    displayThreadingPattern() {
        let canvas = document.getElementById("threading_canvas")
        let ctx = canvas.getContext("2d")
        ctx.clearRect(0, 0, canvas.width, canvas.height)

        canvas.width = 101
        canvas.height = 51
        let rect = document.getElementById("threading_canvas_container").getBoundingClientRect()
        canvas.width = asOdd(rect.width - 2)  // 2 for 1px border
        canvas.height = asOdd(rect.height - 2)  // 2 for 1px border

        if (!this.currentPattern) {
            return
        }
        let endNumber0 = this.currentPattern.end_number0
        let endNumber1 = this.currentPattern.end_number1
        let isJump = false
        if (this.jumpEndNumber0 != null) {
            isJump = true
            endNumber0 = this.jumpEndNumber0
            endNumber1 = this.jumpEndNumber1
        }
        const centerEndNumber = Math.round(Math.max(0, (endNumber0 + endNumber1 - 1) / 2))
        ctx.font = EndFont
        ctx.textBaseline = "middle"
        ctx.textAlign = "center"
        const fontMeas = ctx.measureText("32")
        let blockWidth = Math.ceil(fontMeas.width) + EndDisplayGap
        if (blockWidth % 2 == 0) {
            blockWidth++
        }
        const blockHalfWidth = (blockWidth - 1) / 2
        let blockHeight = Math.ceil(fontMeas.actualBoundingBoxAscent + fontMeas.actualBoundingBoxDescent)
        if (blockHeight % 2 == 0) {
            blockHeight++
        }
        const numEnds = this.currentPattern.warp_colors.length
        const remainingHeight = canvas.height - (blockHeight + fontMeas.actualBoundingBoxAscent + fontMeas.actualBoundingBoxDescent)
        const maxShaftNum = Math.max(...this.currentPattern.threading) + 1
        const verticalDelta = Math.floor(Math.min(blockHeight, remainingHeight / maxShaftNum))

        const numEndsToShow = Math.min(numEnds, Math.floor(canvas.width / blockWidth))

        const centerSlotIndex = Math.round((numEndsToShow - 1) / 2)

        let minDarkEndIndex = endNumber0 - 1
        let maxDarkEndIndex = endNumber1 - 2

        // Display end number above two ends:
        // * The right-most in the range (endNumber0) if nonzero, else end 1
        // * The left-most in the range (endNumber1-1) unless current group size < 4
        //   (i.e. endNumber1 - endNumber0 < 4) because of crowding
        let displayEndIndex0 = endNumber0 - 1
        let displayEndIndex1 = endNumber1 - 2
        if (endNumber0 == 0) {
            displayEndIndex0 = 0
            displayEndIndex1 = null
        } else if (endNumber1 - endNumber0 < 4) {
            displayEndIndex1 = null
        }
        for (let slotIndex = 0; slotIndex < numEndsToShow; slotIndex++) {
            const endIndex = centerEndNumber + slotIndex - centerSlotIndex - 1

            if (endIndex < 0 || endIndex >= this.currentPattern.threading.length) {
                continue
            }
            if (isJump || (endIndex < minDarkEndIndex) || (endIndex > maxDarkEndIndex)) {
                ctx.globalAlpha = 0.3
            } else {
                ctx.globalAlpha = 1.0
            }

            const shaftIndex = this.currentPattern.threading[endIndex]

            const xCenter = canvas.width - blockWidth * slotIndex - blockHalfWidth
            const yCenter = canvas.height - verticalDelta * (shaftIndex + 0.5) - fontMeas.actualBoundingBoxDescent

            if (endIndex == displayEndIndex0) {
                ctx.fillStyle = "black"
                ctx.fillText(endIndex + 1,
                    xCenter,
                    fontMeas.actualBoundingBoxAscent + 2,
                )
                if (endNumber0 > 0) {
                    ctx.strokeRect(
                        xCenter + blockHalfWidth,
                        blockHeight + 2,
                        - blockWidth * (endNumber1 - endNumber0),
                        canvas.height - blockHeight - 2,
                    )
                }
            } else if (endIndex == displayEndIndex1) {
                ctx.fillStyle = "black"
                ctx.fillText(endIndex + 1,
                    xCenter,
                    fontMeas.actualBoundingBoxAscent + 2,
                )
            }

            // Display weft (end) color as bars above and below the shaft number
            const xStart = xCenter - ThreadHalfWidth
            const xEnd = xCenter + ThreadHalfWidth
            const endColor = this.currentPattern.color_table[this.currentPattern.warp_colors[endIndex]]
            let endGradient = ctx.createLinearGradient(xStart, 0, xEnd, 0)
            endGradient.addColorStop(0, "lightgray")
            endGradient.addColorStop(0.2, endColor)
            endGradient.addColorStop(0.8, endColor)
            endGradient.addColorStop(1, "darkgray")

            ctx.fillStyle = endGradient
            ctx.fillRect(
                xCenter - ThreadHalfWidth,
                blockHeight + 2,
                ThreadHalfWidth * 2,
                yCenter - Math.round(blockHeight / 2) - blockHeight - 4,
            )
            ctx.fillRect(
                xCenter - ThreadHalfWidth,
                yCenter + Math.round(blockHeight / 2) + 2,
                ThreadHalfWidth * 2,
                canvas.height - (yCenter + Math.round(blockHeight / 2) + 2)
            )

            // Display shaft number
            ctx.fillStyle = "black"
            ctx.fillText(shaftIndex + 1,
                xCenter,
                yCenter
            )
        }
    }

    displayLoomInfo() {
        let loominfoElt = document.getElementById("loom_info")
        if (this.loomInfo == null) {
            loominfoElt.textContent = ""
        } else {
            loominfoElt.textContent = `${this.loomInfo.name} ${this.loomInfo.num_shafts}`
        }
    }

    // Display the weave direction -- the value of the global "weaveForward" 
    displayWeaveDirection() {
        let weaveDirectionElt = document.getElementById("weave_direction")
        if (this.weaveForward) {
            weaveDirectionElt.textContent = "↓"
            weaveDirectionElt.style.color = "green"
        } else {
            weaveDirectionElt.textContent = "↑"
            weaveDirectionElt.style.color = "red"
        }
    }

    /*
    Display weaving pattern on the "pattern_canvas" element.
     
    Center the jump or current pick vertically.
    */
    displayWeavingPattern() {
        let pickColorElt = document.getElementById("pick_color")
        let canvas = document.getElementById("pattern_canvas")

        let ctx = canvas.getContext("2d")
        ctx.clearRect(0, 0, canvas.width, canvas.height)

        canvas.width = 101
        canvas.height = 51

        let rect = document.getElementById("pattern_canvas_container").getBoundingClientRect()
        canvas.width = asOdd(rect.width - 2)  // 2 for 1px border
        canvas.height = asOdd(rect.height - 2)  // 2 for 1px border

        if (!this.currentPattern) {
            pickColorElt.style.backgroundColor = "rgb(0, 0, 0, 0)"
            return
        }
        let centerPickNumber = this.currentPattern.pick_number
        let isJump = false
        if (this.jumpPickNumber != null) {
            isJump = true
            centerPickNumber = this.jumpPickNumber
        }
        if ((centerPickNumber > 0) && (centerPickNumber <= this.currentPattern.picks.length)) {
            const pick = this.currentPattern.picks[centerPickNumber - 1]
            pickColorElt.style.backgroundColor = this.currentPattern.color_table[pick.color]
        } else {
            pickColorElt.style.backgroundColor = "rgb(0, 0, 0, 0)"
        }
        const numEnds = this.currentPattern.warp_colors.length
        const numPicks = this.currentPattern.picks.length
        let blockSize = Math.min(
            Math.max(Math.round(canvas.width / numEnds), MinBlockSize),
            Math.max(Math.round(canvas.height / numPicks), MinBlockSize),
            MaxBlockSize)
        // Make sure blockSize is odd
        if (blockSize % 2 == 0) {
            blockSize -= 1
        }

        const numEndsToShow = Math.min(numEnds, Math.floor(canvas.width / blockSize))
        // Make sure numPicksToShow is odd
        let numPicksToShow = Math.min(numPicks, Math.ceil(canvas.height / blockSize))
        if (numPicksToShow % 2 == 0) {
            numPicksToShow += 1
        }

        let warpGradients = {}
        for (let i = 0; i < numEndsToShow; i++) {
            const threadColor = this.currentPattern.color_table[this.currentPattern.warp_colors[i]]
            const xStart = canvas.width - blockSize * (i + 1)
            let warpGradient = ctx.createLinearGradient(xStart + ThreadDisplayGap, 0, xStart + blockSize - (2 * ThreadDisplayGap), 0)
            warpGradient.addColorStop(0, "lightgray")
            warpGradient.addColorStop(0.2, threadColor)
            warpGradient.addColorStop(0.8, threadColor)
            warpGradient.addColorStop(1, "darkgray")
            warpGradients[i] = warpGradient
        }

        let yOffset = Math.floor((canvas.height - (blockSize * numPicksToShow)) / 2)
        let startPick = centerPickNumber - ((numPicksToShow - 1) / 2)

        let maxColoredPickIndex = centerPickNumber - 1
        if (isJump) {
            maxColoredPickIndex -= 1
        }
        for (let pickOffset = 0; pickOffset < numPicksToShow; pickOffset++) {
            const pickIndex = startPick + pickOffset - 1

            if (pickIndex < 0 || pickIndex >= this.currentPattern.picks.length) {
                continue
            }
            if (pickIndex > maxColoredPickIndex) {
                ctx.globalAlpha = 0.3
            } else {
                ctx.globalAlpha = 1.0
            }

            const yStart = canvas.height - (yOffset + (blockSize * (pickOffset + 1)))
            let pickGradient = ctx.createLinearGradient(0, yStart + ThreadDisplayGap, 0, yStart + blockSize - (2 * ThreadDisplayGap))
            const pickColor = this.currentPattern.color_table[this.currentPattern.picks[pickIndex].color]
            pickGradient.addColorStop(0, "lightgray")
            pickGradient.addColorStop(0.2, pickColor)
            pickGradient.addColorStop(0.8, pickColor)
            pickGradient.addColorStop(1, "gray")

            const shaft_word = this.currentPattern.picks[pickIndex].shaft_word
            for (let end = 0; end < numEndsToShow; end++) {
                const shaft = this.currentPattern.threading[end]
                if (shaft_word & (1n << BigInt(shaft))) {
                    // Display warp end
                    ctx.fillStyle = warpGradients[end]
                    ctx.fillRect(
                        canvas.width - blockSize * (end + 1) + ThreadDisplayGap,
                        yStart,
                        blockSize - (2 * ThreadDisplayGap),
                        blockSize)
                } else {
                    // Display weft pick
                    ctx.fillStyle = pickGradient
                    ctx.fillRect(
                        canvas.width - blockSize * (end + 1),
                        yStart + ThreadDisplayGap,
                        blockSize,
                        blockSize - (2 * ThreadDisplayGap))
                }
            }

        }

        ctx.globalAlpha = 1.0
        if (isJump) {
            // Jump pick: draw a dashed line around the (centered) jump pick,
            // and, if on the canvas, a solid line around the current pick
            const jumpPickOffset = this.jumpPickNumber - startPick
            ctx.setLineDash([1, 3])
            ctx.strokeRect(
                0,
                canvas.height - (yOffset + (blockSize * (jumpPickOffset + 1))),
                canvas.width,
                blockSize)
            ctx.setLineDash([])
            const currentPickOffset = this.currentPattern.pick_number - startPick
            if ((currentPickOffset >= 0) && (currentPickOffset < numPicksToShow)) {
                ctx.strokeRect(
                    0,
                    canvas.height - (yOffset + (blockSize * (currentPickOffset + 1))),
                    canvas.width,
                    blockSize)
            }
        } else {
            // No jump pick number; draw a solid line around the (centered) current pick
            ctx.setLineDash([])
            const currentPickOffset = this.currentPattern.pick_number - startPick
            ctx.strokeRect(
                0,
                canvas.height - (yOffset + (blockSize * (currentPickOffset + 1))),
                canvas.width,
                blockSize)
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
    Handle pattern files dropped on drop area (likely the whole page)
    */
    async handleDrop(event) {
        await this.handleFileList(event.dataTransfer.files)
    }

    /*
    Handle pattern files from the file_list button
    */
    async handleFileInput(event) {
        await this.handleFileList(event.target.files)
    }

    /*
    Handle pattern file upload from the button and drag-and-drop
    (the latter after massaging the data with handleDrop).
    
    Send the "file" and "select_pattern" commands.
    */
    async handleFileList(fileList) {
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
                const fileCommand = { "type": "file", "name": file.name, "data": data }
                let replyDict = await this.sendCommandAndWait(fileCommand, t("Upload") + ` "${file.name}"`)
                if (!replyDict.success) {
                    return
                }
                if (isFirst) {
                    isFirst = false
                    const selectPatternCommand = { "type": "select_pattern", "name": file.name }
                    replyDict = await this.sendCommandAndWait(selectPatternCommand, t("Select") + ` "${file.name}"`)
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

    /*
    Handle the thread group size select menu
    */
    async handleThreadGroupSize(event) {
        const patternMenu = document.getElementById("thread_group_size")
        const command = { "type": "thread_group_size", "group_size": Number(patternMenu.value) }
        await this.sendCommand(command)
    }


    /*
    Handle user editing of jump_end_number and jump_end_repeat_number.
    */
    async handleJumpToEndInput(event) {
        let jumpToEndSubmitElt = document.getElementById("jump_to_end_submit")
        let jumpToEndResetElt = document.getElementById("jump_to_end_reset")
        let jumpEndNumber0Elt = document.getElementById("jump_end_number0")
        let jumpEndRepeatNumberElt = document.getElementById("jump_end_repeat_number")
        let disableJump = true
        if (asNumberOrNull(jumpEndNumber0Elt.value) != this.jumpEndNumber) {
            jumpEndNumber0Elt.style.backgroundColor = "pink"
            disableJump = false
        } else {
            jumpEndNumber0Elt.style.backgroundColor = "white"
        }
        if (asNumberOrNull(jumpEndRepeatNumberElt.value) != this.jumpEndRepeatNumber) {
            jumpEndRepeatNumberElt.style.backgroundColor = "pink"
            disableJump = false
        } else {
            jumpEndRepeatNumberElt.style.backgroundColor = "white"
        }
        let disableReset = disableJump && (jumpEndNumber0Elt.value == "") && (jumpEndRepeatNumberElt.value == "")
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
        const jumpEndNumber0Elt = document.getElementById("jump_end_number0")
        const jumpEndRepeatNumberElt = document.getElementById("jump_end_repeat_number")
        jumpEndNumber0Elt.value = ""
        jumpEndRepeatNumberElt.value = ""
        const command = { "type": "jump_to_end", "end_number0": null, "end_repeat_number": null }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle jump_to_end form submit.
    
    Send the "jump_to_end" command.
    */
    async handleJumpToEndSubmit(event) {
        const jumpEndNumber0Elt = document.getElementById("jump_end_number0")
        const jumpEndRepeatNumberElt = document.getElementById("jump_end_repeat_number")
        // Handle blanks by using the current default, if any
        const endNumber0 = asNumberOrNull(jumpEndNumber0Elt.value)
        const repeatNumber = asNumberOrNull(jumpEndRepeatNumberElt.value)
        const command = { "type": "jump_to_end", "end_number0": endNumber0, "end_repeat_number": repeatNumber }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle user editing of jump_pick_number and jump_pick_repeat_number.
    */
    async handleJumpToPickInput(event) {
        let jumpToPickSubmitElt = document.getElementById("jump_to_pick_submit")
        let jumpToPickResetElt = document.getElementById("jump_to_pick_reset")
        let jumpPickNumberElt = document.getElementById("jump_pick_number")
        let jumpPickRepeatNumberElt = document.getElementById("jump_pick_repeat_number")
        let disableJump = true
        if (asNumberOrNull(jumpPickNumberElt.value) != this.jumpPickNumber) {
            jumpPickNumberElt.style.backgroundColor = "pink"
            disableJump = false
        } else {
            jumpPickNumberElt.style.backgroundColor = "white"
        }
        if (asNumberOrNull(jumpPickRepeatNumberElt.value) != this.jumpPickRepeatNumber) {
            jumpPickRepeatNumberElt.style.backgroundColor = "pink"
            disableJump = false
        } else {
            jumpPickRepeatNumberElt.style.backgroundColor = "white"
        }
        let disableReset = disableJump && (jumpPickNumberElt.value == "") && (jumpPickRepeatNumberElt.value == "")
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
        const jumpPickNumberElt = document.getElementById("jump_pick_number")
        const jumpPickRepeatNumberElt = document.getElementById("jump_pick_repeat_number")
        jumpPickNumberElt.value = ""
        jumpPickRepeatNumberElt.value = ""
        const command = { "type": "jump_to_pick", "pick_number": null, "pick_repeat_number": null }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle jump_to_pick form submit.
    
    Send the "jump_to_pick" command.
    */
    async handleJumpToPickSubmit(event) {
        const jumpPickNumberElt = document.getElementById("jump_pick_number")
        const jumpPickRepeatNumberElt = document.getElementById("jump_pick_repeat_number")
        // Handle blanks by using the current default, if any
        const pickNumber = asNumberOrNull(jumpPickNumberElt.value)
        const repeatNumber = asNumberOrNull(jumpPickRepeatNumberElt.value)
        const command = { "type": "jump_to_pick", "pick_number": pickNumber, "pick_repeat_number": repeatNumber }
        await this.sendCommand(command)
        event.preventDefault()
    }


    /*
    Handle the OOB change direction button.
    
    Send "oobcommand" command "d".
    */
    async handleOOBChangeDirection(event) {
        let command = { "type": "oobcommand", "command": "d" }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle the OOB close connection button.
    
    Send "oobcommand" command "c".
    */
    async handleOOBCloseConnection(event) {
        let command = { "type": "oobcommand", "command": "c" }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle the OOB next pick button.
    
    Send "oobcommand" command "n".
    */
    async handleOOBNextPick(event) {
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
    Handle the mode tab bar buttons

    Mode us a ModeEnum value
    */
    async handleMode(mode, event) {
        const command = { "type": "mode", "mode": mode }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle thread_direction button clicks.
    
    Send the weave_direction command to the loom server.
    */
    async handleToggleThreadDirection(event) {
        let threadDirectionElt = document.getElementById("thread_direction")
        let newLowToHigh = (threadDirectionElt.textContent == "→") ? true : false
        let command = { "type": "thread_direction", "low_to_high": newLowToHigh }
        await this.sendCommand(command)
    }

    /*
    Handle weave_direction button clicks.
    
    Send the weave_direction command to the loom server.
    */
    async handleToggleWeaveDirection(event) {
        let weaveDirectionElt = document.getElementById("weave_direction")
        let newForward = (weaveDirectionElt.textContent == "↑") ? true : false
        let command = { "type": "weave_direction", "forward": newForward }
        await this.sendCommand(command)
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
    async sendCommandAndWait(commandDict, description, timeoutMs = 5000) {
        if (description == null) {
            description = commandDict.type
        }
        let oldFuture = this.commandFutures[commandDict.type]
        if ((oldFuture != null) && (!oldFuture.done)) {
            oldFuture.setException(Error("superseded"))
        }
        let newFuture = new Future(description, timeoutMs)
        this.commandFutures[commandDict.type] = newFuture
        await this.sendCommand(commandDict)
        return newFuture
    }
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
Return "" if value is null, else return value
*/
function nullToBlank(value) {
    return value == null ? "" : value
}

/*
Return null if value is "", else return Number(value)
*/
function asNumberOrNull(value) {
    return value == "" ? null : Number(value)
}

//
function preventDefaults(event) {
    event.preventDefault()
    event.stopPropagation()
}

// Async wrapper around FileReader.readAsText
// from https://masteringjs.io/tutorials/fundamentals/filereader#:~:text=The%20FileReader%20class%27%20async%20API%20isn%27t%20ideal,for%20usage%20with%20async%2Fawait%20or%20promise%20chaining.
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

// Read a binary file and encode it using base64
// The encoding algorithm is from https://stackoverflow.com/a/58339391/1653413
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

loomClient = new LoomClient()
loomClient.init()
