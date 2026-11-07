#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use std::sync::Mutex;
use tauri::Manager;

#[derive(Clone, serde::Serialize)]
struct Connection { url: String, token: String }
struct Engine {
    child: Mutex<Option<std::process::Child>>,
    connection: Option<Connection>,
    error: Option<String>,
    connection_file: Option<std::path::PathBuf>,
}

#[tauri::command]
fn desktop_connection(engine: tauri::State<Engine>) -> Result<Option<Connection>, String> {
    match &engine.error {
        Some(error) => Err(error.clone()),
        None => Ok(engine.connection.clone()),
    }
}

#[cfg(all(windows, not(debug_assertions)))]
fn start_engine(app: &tauri::App) -> Result<Engine, Box<dyn std::error::Error>> {
    use std::os::windows::process::CommandExt;
    let home = match std::env::var("OMNIDEV_HOME") {
        Ok(path) => std::path::PathBuf::from(path),
        Err(_) => std::path::PathBuf::from(std::env::var("USERPROFILE")?).join(".omnidev"),
    };
    std::fs::create_dir_all(&home)?;
    let port = std::net::TcpListener::bind("127.0.0.1:0")?.local_addr()?.port();
    let token = uuid::Uuid::new_v4().simple().to_string();
    let executable = app.path().resource_dir()?.join("engine").join("omnidev-cli.exe");
    let log = std::fs::OpenOptions::new().create(true).append(true).open(home.join("desktop-engine.log"))?;
    let child = std::process::Command::new(executable)
        .args(["serve", "--host", "127.0.0.1", "--port", &port.to_string()])
        .env("OMNIDEV_HOME", &home).env("API_TOKEN", &token)
        .current_dir(&home).stdin(std::process::Stdio::null())
        .stdout(log.try_clone()?).stderr(log).creation_flags(0x08000000).spawn()?;
    Ok(Engine { child: Mutex::new(Some(child)), connection: Some(Connection { url: format!("http://127.0.0.1:{port}"), token }), error: None, connection_file: Some(home.join("desktop-connection.json")) })
}

#[tauri::command]
fn engine_ready(engine: tauri::State<Engine>) -> Result<(), String> {
    // Publish the CLI connection only after the renderer observed a healthy API.
    if let (Some(path), Some(connection)) = (&engine.connection_file, &engine.connection) {
        let json = format!("{{\"url\":\"{}\",\"token\":\"{}\"}}", connection.url, connection.token);
        std::fs::write(path, json).map_err(|_| "Could not save the CLI connection".to_string())?;
    }
    Ok(())
}

fn stop_engine(engine: &Engine) {
    if let Ok(mut guard) = engine.child.lock() {
        if let Some(mut child) = guard.take() {
            #[cfg(windows)]
            {
                use std::os::windows::process::CommandExt;
                let _ = std::process::Command::new("taskkill").args(["/PID", &child.id().to_string(), "/T", "/F"]).creation_flags(0x08000000).output();
            }
            let _ = child.kill();
            let _ = child.wait();
        }
    }
    if let Some(path) = &engine.connection_file { let _ = std::fs::remove_file(path); }
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, _, _| {
            if let Some(window) = app.get_webview_window("main") { let _ = window.set_focus(); }
        }))
        .setup(|app| {
            #[cfg(all(windows, not(debug_assertions)))]
            let engine = start_engine(app).unwrap_or_else(|error| Engine { child: Mutex::new(None), connection: None, error: Some(format!("The local engine could not start: {error}")), connection_file: None });
            #[cfg(any(not(windows), debug_assertions))]
            let engine = Engine { child: Mutex::new(None), connection: None, error: None, connection_file: None };
            app.manage(engine);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![desktop_connection, engine_ready])
        .build(tauri::generate_context!()).expect("Unable to start OmniDev")
        .run(|app, event| { if let tauri::RunEvent::Exit = event { stop_engine(&app.state::<Engine>()); } });
}
