using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

static class Launcher {
    [STAThread]
    static void Main(string[] args) {
        string root = AppDomain.CurrentDomain.BaseDirectory;
        string engine = Path.Combine(root, "runtime", "Godot.exe");
        string project = Path.Combine(root, "game");
        if (!File.Exists(engine) || !File.Exists(Path.Combine(project, "project.godot"))) {
            MessageBox.Show("Extrayez le dossier complet avant de lancer la prévisualisation.", "ChaosticTool");
            return;
        }
        string extra = "";
        // Only the owned validation mode accepts an argument; never invoke a shell.
        if (args.Length == 1 && args[0].StartsWith("--qa-dir=") && !args[0].Contains("\""))
            extra = " -- \"" + args[0] + "\"";
        var start = new ProcessStartInfo(engine, "--path \"" + project + "\"" + extra);
        start.UseShellExecute = false;
        start.CreateNoWindow = true;
        start.WorkingDirectory = project;
        try { Process.Start(start); }
        catch (Exception ex) { MessageBox.Show(ex.Message, "ChaosticTool — démarrage impossible"); }
    }
}
