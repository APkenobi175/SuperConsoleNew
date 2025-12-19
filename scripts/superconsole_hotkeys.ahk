#Requires AutoHotkey v2.0
#SingleInstance Force
SetTitleMatchMode 2
DetectHiddenWindows True

^+q:: {
    try ProcessClose("Dolphin.exe")
    try ProcessClose("Cemu.exe")
    try ProcessClose("pcsx2-qt.exe")
    try ProcessClose("rpcs3.exe")
    try ProcessClose("xemu.exe")
    try ProcessClose("xenia.exe")
    try ProcessClose("duckstation-qt-x64-ReleaseLTCG.exe")
    try ProcessClose("Project64.exe")
    try ProcessClose("mupen64plus-ui-console.exe")
    try ProcessClose("mGBA.exe")
    try ProcessClose("mgba-sdl.exe")
    try ProcessClose("Mesen.exe")
    try ProcessClose("bsnes.exe")
    ; WSL: only kill emulators. Restoring launcher focus is flaky there.
    if WinExist("SuperConsole")
    {
        try WinShow("SuperConsole")
        try WinRestore("SuperConsole")
        try WinActivate("SuperConsole")
        try WinWaitActive("SuperConsole",, 2)
        try WinMaximize("SuperConsole")
    }
}
