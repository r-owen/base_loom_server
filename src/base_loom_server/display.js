// The following line is replaced by python code, so don't change it
const TranslationDict = {}

const MaxFiles = 10

const MinBlockSize = 11
const MaxBlockSize = 41
// Display gap on left and right edges of warp and top and bottom edges of weft
const ThreadDisplayGap = 1

// Keys are the possible values of the LoomConnectionState.state messages
// Values are entries in ConnectionStateEnum
const ConnectionStateTranslationDict = {
    0: "disconnected",
    1: "connected",
    2: "connecting",
    3: "disconnecting",
}

const SeverityColors = {
    1: "#ffffff",
    2: "yellow",
    3: "red",
}

const ShaftStateTranslationDict = {
    0: "?",
    1: "done",
    2: "moving",
    3: "error",
}

var ConnectionStateEnum = {}
for (let i = 0; i < Object.keys(ConnectionStateTranslationDict).length; ++i) {
    var name = ConnectionStateTranslationDict[i]
    ConnectionStateEnum[name] = name
}
Object.freeze(ConnectionStateEnum)

const numericCollator = new Intl.Collator(undefined, { numeric: true })

function t(phrase) {
    if (!(phrase in TranslationDict)) {
        console.log("Missing translation key:", phrase)
        return phrase
    }
    return TranslationDict[phrase]
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
        this.repeat_number = datadict.repeat_number
        datadict.picks.forEach((pickdata) => {
            this.picks.push(new Pick(pickdata))
        })
        this.warpGradients = {}
    }
}

/*
Data for a pick
*/
class Pick {
    constructor(datadict) {
        this.color = datadict.color
        this.shaft_word = Number(datadict.shaft_word)
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
This version does not work, because "this" is the wrong thing in callbacks.
But it could probably be easily made to work by adding a
"addEventListener method that takes an id, an event name, and a function
and uses "bind" in the appropriate fashion.

The result might be a nice -- each assignment would be a single line.
*/

class LoomClient {
    constructor() {
        this.ws = new WebSocket("ws")
        this.currentPattern = null
        this.weaveForward = true
        this.loomConnectionState = ConnectionStateEnum.disconnected
        this.loomConnectionStateReason = ""
        this.statusMessage = null
        this.jumpPickNumber = null
        this.jumpRepeatNumber = null
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

        var fileInputElt = document.getElementById("file_input")
        fileInputElt.addEventListener("change", this.handleFileInput.bind(this))

        var jumpToPickForm = document.getElementById("jump_to_pick_form")
        jumpToPickForm.addEventListener("submit", this.handleJumpToPick.bind(this))

        var jumpToPickResetElt = document.getElementById("jump_to_pick_reset")
        jumpToPickResetElt.addEventListener("click", this.handleJumpToPickReset.bind(this))

        // Select all text on focus, to make it easier to try different jump values
        // (without this, you are likely to append digits, which is rarely what you want)
        var jumpPickNumberElt = document.getElementById("jump_pick_number")
        jumpPickNumberElt.addEventListener(`focus`, () => jumpPickNumberElt.select())

        var jumpRepeatNumberElt = document.getElementById("jump_repeat_number")
        jumpRepeatNumberElt.addEventListener(`focus`, () => jumpRepeatNumberElt.select())

        var oobChangeDirectionButton = document.getElementById("oob_change_direction")
        oobChangeDirectionButton.addEventListener("click", this.handleOOBChangeDirection.bind(this))

        var oobCloseConnectionButton = document.getElementById("oob_close_connection")
        oobCloseConnectionButton.addEventListener("click", this.handleOOBCloseConnection.bind(this))

        var oobNextPickButton = document.getElementById("oob_next_pick")
        oobNextPickButton.addEventListener("click", this.handleOOBNextPick.bind(this))

        var weaveDirectionElt = document.getElementById("weave_direction")
        weaveDirectionElt.addEventListener("click", this.handleToggleWeaveDirection.bind(this))

        var jumpPickNumberElt = document.getElementById("jump_pick_number")
        jumpPickNumberElt.addEventListener("input", this.handleJumpInput.bind(this))

        var jumpRepeatNumberElt = document.getElementById("jump_repeat_number")
        jumpRepeatNumberElt.addEventListener("input", this.handleJumpInput.bind(this))

        var patternMenu = document.getElementById("pattern_menu")
        patternMenu.addEventListener("change", this.handlePatternMenu.bind(this))
    }

    /*
    Process a reply from the loom server (data read from the web socket)
    */
    handleServerReply(event) {
        var messageElt = document.getElementById("read_message")
        if (event.data.length <= 80) {
            messageElt.textContent = event.data
        } else {
            messageElt.textContent = event.data.substring(0, 80) + "..."
        }
        var commandProblemElt = document.getElementById("command_problem")

        const datadict = JSON.parse(event.data)
        var resetCommandProblemMessage = true
        if (datadict.type == "CurrentPickNumber") {
            if (!this.currentPattern) {
                console.log("Ignoring CurrentPickNumber: no pattern loaded")
            }
            this.currentPattern.pick_number = datadict.pick_number
            this.currentPattern.repeat_number = datadict.repeat_number
            this.displayCurrentPattern()
            this.displayPick()
        } else if (datadict.type == "JumpPickNumber") {
            this.jumpPickNumber = datadict.pick_number
            this.jumpRepeatNumber = datadict.repeat_number
            this.displayJumpPick()
        } else if (datadict.type == "LoomConnectionState") {
            this.loomConnectionState = datadict
            this.loomConnectionState.state = ConnectionStateTranslationDict[datadict.state]
            this.displayStatusMessage()
        } else if (datadict.type == "ShaftState") {
            this.displayShaftState(datadict)
        } else if (datadict.type == "StatusMessage") {
            resetCommandProblemMessage = false
            this.statusMessage = datadict
            this.displayStatusMessage()
        } else if (datadict.type == "ReducedPattern") {
            this.currentPattern = new ReducedPattern(datadict)
            this.displayCurrentPattern()
            var patternMenu = document.getElementById("pattern_menu")
            patternMenu.value = this.currentPattern.name
        } else if (datadict.type == "PatternNames") {
            /*
            Why this code is so odd:
            • The <hr> separator is not part of option list, and there is no good way
              to add a separator in javascript, so I preserve the old one.
            • The obvious solution is to remove the old names, then insert new ones.
              Unfortunately that loses the <hr> separator.
            • So I insert the new names, then remove the old ones. Ugly, but at least
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
            var patternMenu = document.getElementById("pattern_menu")
            var patternNames = datadict.names
            var menuOptions = patternMenu.options
            var currentName = this.currentPattern ? this.currentPattern.name : ""

            // This preserves the separator if called with no names
            if (patternNames.length == 0) {
                patternNames.push("")
            }

            // Save this value for later deletion of old pattern names
            var numOldPatternNames = patternMenu.options.length - 1

            // Insert new pattern names
            for (let i = 0; i < patternNames.length; i++) {
                var patternName = patternNames[i]
                var option = new Option(patternName)
                menuOptions.add(option, 0)
            }

            // Purge old pattern names
            for (let i = patternNames.length; i < patternNames.length + numOldPatternNames; i++) {
                menuOptions.remove(patternNames.length)
            }
            patternMenu.value = currentName
        } else if (datadict.type == "CommandProblem") {
            resetCommandProblemMessage = false
            var color = SeverityColors[datadict.severity]
            if (color == null) {
                color = "#ffffff"
            }
            commandProblemElt.textContent = datadict.message
            commandProblemElt.style.color = color
        } else if (datadict.type == "WeaveDirection") {
            this.weaveForward = datadict.forward
            this.displayDirection()
        } else {
            console.log("Unknown message type", datadict.type)
        }
        if (resetCommandProblemMessage) {
            commandProblemElt.textContent = ""
            commandProblemElt.style.color = "#ffffff"
        }
    }

    // Display the weave direction -- the value of the global "weaveForward" 
    displayDirection() {
        var weaveDirectionElt = document.getElementById("weave_direction")
        if (this.weaveForward) {
            weaveDirectionElt.textContent = "↓"
            weaveDirectionElt.style.color = "green"
        } else {
            weaveDirectionElt.textContent = "↑"
            weaveDirectionElt.style.color = "red"
        }
    }

    isConnected() {
        return this.loomConnectionState.state == ConnectionStateEnum.connected
    }

    /*
    Display ShaftState
    */
    displayShaftState(datadict) {
        var text = ""
        var textColor = "black"
        if (datadict.state == 1) {
            // Move is done; display shaft numbers
            var raisedShaftList = []
            var bitmask = datadict.shaft_word
            var shaft_number = 1

            while (bitmask !== 0) {
                if (bitmask & 1) {
                    raisedShaftList.push(shaft_number)
                }
                bitmask >>= 1
                shaft_number++
            }
            text = raisedShaftList.join(", ")
        } else {
            text = t(ShaftStateTranslationDict[datadict.state])
            if (datadict.state == 3) {
                textColor = "red"
            }
        }
        var shaftStateElt = document.getElementById("shaft_state")
        shaftStateElt.textContent = text
        shaftStateElt.style.color = textColor
    }

    /*
    Display the status message (a combination of self.loomConnectionState and self.statusMessage)
    */
    displayStatusMessage() {
        var text = t(this.loomConnectionState.state)
        var textColor = "black"
        if (this.isConnected() && (this.statusMessage != null)) {
            text = this.statusMessage.message
            textColor = SeverityColors[datadict.severity]
        } else if (!this.isConnected()) {
            this.statusMessage = null
            textColor = "red"  // loom must be connected to weave
        }
        var statusElt = document.getElementById("status")
        statusElt.textContent = text
        statusElt.style.color = textColor
    }

    /*
    Display a portion of weavingPattern on the "canvas" element.

    Center the jump or current pick vertically.
    */
    displayCurrentPattern() {
        var canvas = document.getElementById("canvas")
        var ctx = canvas.getContext("2d")
        if (!this.currentPattern) {
            context.clearRect(0, 0, canvas.width, canvas.height)
            return
        }
        var pickColorElt = document.getElementById("pick_color")
        var centerPickNumber = this.currentPattern.pick_number
        var isJump = false
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
        var canvas = document.getElementById("canvas")
        var ctx = canvas.getContext("2d")
        const numEnds = this.currentPattern.warp_colors.length
        const numPicks = this.currentPattern.picks.length
        var blockSize = Math.min(
            Math.max(Math.round(canvas.width / numEnds), MinBlockSize),
            Math.max(Math.round(canvas.height / numPicks), MinBlockSize),
            MaxBlockSize)
        // Make sure blockSize is odd
        if (blockSize % 2 == 0) {
            blockSize -= 1
        }

        const numEndsToShow = Math.min(numEnds, Math.floor(canvas.width / blockSize))
        // Make sure numPicksToShow is odd
        var numPicksToShow = Math.min(numPicks, Math.ceil(canvas.height / blockSize))
        if (numPicksToShow % 2 == 0) {
            numPicksToShow += 1
        }

        // If not yet done, create warp gradients for those warps what will be shown
        if (this.currentPattern.warpGradients[0] == undefined) {
            for (let i = 0; i < numEndsToShow; i++) {
                const threadColor = this.currentPattern.color_table[this.currentPattern.warp_colors[i]]
                const xStart = canvas.width - blockSize * (i + 1)
                var warpGradient = ctx.createLinearGradient(xStart + ThreadDisplayGap, 0, xStart + blockSize - (2 * ThreadDisplayGap), 0)
                warpGradient.addColorStop(0, "white")
                warpGradient.addColorStop(0.2, threadColor)
                warpGradient.addColorStop(0.8, threadColor)
                warpGradient.addColorStop(1, "gray")
                this.currentPattern.warpGradients[i] = warpGradient
            }
        }
        var yOffset = Math.floor((canvas.height - (blockSize * numPicksToShow)) / 2)
        var startPick = centerPickNumber - ((numPicksToShow - 1) / 2)
        ctx.clearRect(0, 0, canvas.width, canvas.height)
        var maxColoredPickIndex = centerPickNumber - 1
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
            var pickGradient = ctx.createLinearGradient(0, yStart + ThreadDisplayGap, 0, yStart + blockSize - (2 * ThreadDisplayGap))
            const pickColor = this.currentPattern.color_table[this.currentPattern.picks[pickIndex].color]
            pickGradient.addColorStop(0, "white")
            pickGradient.addColorStop(0.2, pickColor)
            pickGradient.addColorStop(0.8, pickColor)
            pickGradient.addColorStop(1, "gray")

            const shaft_word = this.currentPattern.picks[pickIndex].shaft_word
            for (let end = 0; end < numEndsToShow; end++) {
                const shaft = this.currentPattern.threading[end]
                if (shaft_word & 1 << shaft) {
                    // Display warp end
                    ctx.fillStyle = this.currentPattern.warpGradients[end]
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
    Display the current pick and repeat.
    */
    displayPick() {
        var repeatNumberElt = document.getElementById("repeat_number")
        var pickNumberElt = document.getElementById("pick_number")
        var totalPicksElt = document.getElementById("total_picks")
        var pickNumber = ""
        var totalPicks = "?"
        var repeatNumber = ""
        if (this.currentPattern) {
            pickNumber = this.currentPattern.pick_number
            repeatNumber = this.currentPattern.repeat_number
            totalPicks = this.currentPattern.picks.length
        }
        pickNumberElt.textContent = pickNumber
        repeatNumberElt.textContent = repeatNumber
        totalPicksElt.textContent = totalPicks
    }

    /*
    Display the jump pick and repeat
    */
    displayJumpPick() {
        var pickNumberElt = document.getElementById("jump_pick_number")
        var repeatNumberElt = document.getElementById("jump_repeat_number")
        if (!this.currentPattern) {
            this.jumpPickNumber = null
            this.jumpRepeatNumber = null
        }
        pickNumberElt.value = nullToBlank(this.jumpPickNumber)
        repeatNumberElt.value = nullToBlank(this.jumpRepeatNumber)
        if (this.currentPattern) {
            this.displayCurrentPattern()
        }
        this.handleJumpInput(null)
    }

    /*
    Handle the pattern_menu select menu.
    
    Send the "select_pattern" or "clear_pattern_names" command.
    */
    async handlePatternMenu(event) {
        var patternMenu = document.getElementById("pattern_menu")
        var command
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
        if (fileList.length > MaxFiles) {
            console.log("Cannot upload more than", MaxFiles, "files at once")
            return
        }
        if (fileList.length == 0) {
            return
        }

        // Sort the file names; this requires a bit of extra work
        // because FileList doesn't support sort.

        var fileArray = Array.from(fileList)
        fileArray.sort(compareFiles)

        for (let i = 0; i < fileArray.length; i++) {
            var file = fileArray[i]
            var data = await readTextFile(file)
            var fileCommand = { "type": "file", "name": file.name, "data": data }
            await this.sendCommand(fileCommand)
        }

        // Select the first file uploaded
        var file = fileArray[0]
        var selectPatternCommand = { "type": "select_pattern", "name": file.name }
        await this.sendCommand(selectPatternCommand)
    }


    /*
    Handle user editing of jump_pick_number and jump_repeat_number.
    */
    async handleJumpInput(event) {
        var jumpToPickSubmitElt = document.getElementById("jump_to_pick_submit")
        var jumpToPickResetElt = document.getElementById("jump_to_pick_reset")
        var jumpPickNumberElt = document.getElementById("jump_pick_number")
        var jumpRepeatNumberElt = document.getElementById("jump_repeat_number")
        var disableJump = true
        if (asNumberOrNull(jumpPickNumberElt.value) != this.jumpPickNumber) {
            jumpPickNumberElt.style.backgroundColor = "pink"
            disableJump = false
        } else {
            jumpPickNumberElt.style.backgroundColor = "white"
        }
        if (asNumberOrNull(jumpRepeatNumberElt.value) != this.jumpRepeatNumber) {
            jumpRepeatNumberElt.style.backgroundColor = "pink"
            disableJump = false
        } else {
            jumpRepeatNumberElt.style.backgroundColor = "white"
        }
        var disableReset = disableJump && (jumpPickNumberElt.value == "") && (jumpRepeatNumberElt.value == "")
        jumpToPickSubmitElt.disabled = disableJump
        jumpToPickResetElt.disabled = disableReset
        if (event != null) {
            event.preventDefault()
        }
    }

    /*
    Handle jump_to_pick form submit.
    
    Send the "jump_to_pick" command.
    */
    async handleJumpToPick(event) {
        var jumpPickNumberElt = document.getElementById("jump_pick_number")
        var jumpRepeatNumberElt = document.getElementById("jump_repeat_number")
        // Handle blanks by using the current default, if any
        var pickNumber = asNumberOrNull(jumpPickNumberElt.value)
        var repeatNumber = asNumberOrNull(jumpRepeatNumberElt.value)
        var command = { "type": "jump_to_pick", "pick_number": pickNumber, "repeat_number": repeatNumber }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle Reset buttin in the "jump_to_pick" form.
    
    Reset pick number and repeat number to current values.
    */
    async handleJumpToPickReset(event) {
        var jumpPickNumberElt = document.getElementById("jump_pick_number")
        var jumpRepeatNumberElt = document.getElementById("jump_repeat_number")
        jumpPickNumberElt.value = ""
        jumpRepeatNumberElt.value = ""
        var command = { "type": "jump_to_pick", "pick_number": null, "repeat_number": null }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle the OOB change direction button.
    
    Send "oobcommand" command "d".
    */
    async handleOOBChangeDirection(event) {
        var command = { "type": "oobcommand", "command": "d" }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle the OOB close connection button.
    
    Send "oobcommand" command "c".
    */
    async handleOOBCloseConnection(event) {
        var command = { "type": "oobcommand", "command": "c" }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle the OOB next pick button.
    
    Send "oobcommand" command "n".
    */
    async handleOOBNextPick(event) {
        var command = { "type": "oobcommand", "command": "n" }
        await this.sendCommand(command)
        event.preventDefault()
    }

    /*
    Handle weave_direction button clicks.
    
    Send the weave_direction command to the loom server.
    */
    async handleToggleWeaveDirection(event) {
        var weaveDirectionElt = document.getElementById("weave_direction")
        var newForward = (weaveDirectionElt.textContent == "↑") ? true : false
        var command = { "type": "weave_direction", "forward": newForward }
        await this.sendCommand(command)
    }

    async sendCommand(commandDict) {
        var commandElt = document.getElementById("sent_command")
        var commandStr = JSON.stringify(commandDict)
        if (commandStr.length <= 80) {
            commandElt.textContent = commandStr
        } else {
            commandElt.textContent = commandStr.substring(0, 80) + "..."
        }
        await this.ws.send(commandStr)
    }
}

/*
Handle websocket close
*/
async function handleWebsocketClosed(event) {
    var statusElt = document.getElementById("status")
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
function readTextFile(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader()

        reader.onload = res => {
            resolve(res.target.result)
        }
        reader.onerror = err => reject(err)

        reader.readAsText(file)
    })
}

loomClient = new LoomClient()
loomClient.init()
