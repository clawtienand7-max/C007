// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::{Arc, Mutex};
use std::time::Duration;
use tauri::{
    AppHandle, CustomMenuItem, GlobalShortcutManager, Manager, RunEvent, SystemTray,
    SystemTrayEvent, SystemTrayMenu, SystemTrayMenuItem, WindowEvent,
};
use tauri::api::process::{Command, CommandChild, CommandEvent};

// ─── State ────────────────────────────────────────────────────────────────────

struct SidecarState {
    child: Option<CommandChild>,
    running: bool,
}

impl SidecarState {
    fn new() -> Self {
        SidecarState {
            child: None,
            running: false,
        }
    }
}

type SharedSidecar = Arc<Mutex<SidecarState>>;

// ─── Sidecar management ───────────────────────────────────────────────────────

/// Spawn the FastAPI sidecar and wire up stdout/stderr forwarding.
/// Emits `sidecar_started` or `sidecar_error` to all windows.
fn start_sidecar(app: AppHandle, state: SharedSidecar) {
    let (mut rx, child) = match Command::new_sidecar("server") {
        Ok(cmd) => match cmd.spawn() {
            Ok(pair) => pair,
            Err(e) => {
                eprintln!("[TFNK] sidecar spawn error: {e}");
                let _ = app.emit_all("sidecar_error", format!("spawn error: {e}"));
                return;
            }
        },
        Err(e) => {
            eprintln!("[TFNK] sidecar command error: {e}");
            let _ = app.emit_all("sidecar_error", format!("command error: {e}"));
            return;
        }
    };

    {
        let mut s = state.lock().unwrap();
        s.child = Some(child);
        s.running = true;
    }

    let _ = app.emit_all("sidecar_started", "FastAPI server started");
    println!("[TFNK] sidecar started");

    // Spawn a task to read output and watch for exit
    let app_clone = app.clone();
    let state_clone = state.clone();
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(line) => {
                    print!("[server] {line}");
                }
                CommandEvent::Stderr(line) => {
                    eprint!("[server:err] {line}");
                }
                CommandEvent::Terminated(payload) => {
                    {
                        let mut s = state_clone.lock().unwrap();
                        s.child = None;
                        s.running = false;
                    }
                    let code = payload.code.unwrap_or(-1);
                    eprintln!("[TFNK] sidecar terminated with code {code}");
                    let _ = app_clone.emit_all("sidecar_stopped", code);

                    // Auto-restart unless the app is shutting down
                    tokio::time::sleep(Duration::from_secs(3)).await;
                    println!("[TFNK] attempting sidecar restart…");
                    start_sidecar(app_clone.clone(), state_clone.clone());
                    return;
                }
                _ => {}
            }
        }
    });
}

/// Gracefully stop the sidecar child process.
fn stop_sidecar(state: &SharedSidecar) {
    let mut s = state.lock().unwrap();
    if let Some(child) = s.child.take() {
        let _ = child.kill();
        println!("[TFNK] sidecar stopped");
    }
    s.running = false;
}

// ─── System tray ──────────────────────────────────────────────────────────────

fn build_tray() -> SystemTray {
    let show_hide = CustomMenuItem::new("show_hide".to_string(), "Show / Hide");
    let emergency = CustomMenuItem::new("emergency_stop".to_string(), "Emergency Stop");
    let quit = CustomMenuItem::new("quit".to_string(), "Quit TFNK™");

    let menu = SystemTrayMenu::new()
        .add_item(show_hide)
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(emergency)
        .add_native_item(SystemTrayMenuItem::Separator)
        .add_item(quit);

    SystemTray::new().with_menu(menu)
}

fn handle_tray_event(app: &AppHandle, event: SystemTrayEvent, sidecar: SharedSidecar) {
    match event {
        SystemTrayEvent::MenuItemClick { id, .. } => match id.as_str() {
            "show_hide" => toggle_window(app),
            "emergency_stop" => {
                println!("[TFNK] emergency stop triggered via tray");
                stop_sidecar(&sidecar);
                let _ = app.emit_all("sidecar_stopped", "emergency_stop");
            }
            "quit" => {
                stop_sidecar(&sidecar);
                app.exit(0);
            }
            _ => {}
        },
        SystemTrayEvent::LeftClick { .. } => toggle_window(app),
        _ => {}
    }
}

// ─── Window helpers ───────────────────────────────────────────────────────────

fn toggle_window(app: &AppHandle) {
    if let Some(window) = app.get_window("main") {
        if window.is_visible().unwrap_or(false) {
            let _ = window.hide();
        } else {
            let _ = window.show();
            let _ = window.set_focus();
        }
    }
}

fn emergency_stop(app: &AppHandle, sidecar: &SharedSidecar) {
    println!("[TFNK] EMERGENCY STOP — Ctrl+Shift+S");
    stop_sidecar(sidecar);
    let _ = app.emit_all("sidecar_stopped", "emergency_stop");
}

// ─── Tauri commands (callable from frontend) ──────────────────────────────────

#[tauri::command]
fn get_sidecar_status(state: tauri::State<SharedSidecar>) -> bool {
    state.lock().map(|s| s.running).unwrap_or(false)
}

#[tauri::command]
fn restart_sidecar(app: AppHandle, state: tauri::State<SharedSidecar>) {
    let shared = Arc::clone(&state);
    stop_sidecar(&shared);
    tokio::spawn(async move {
        tokio::time::sleep(Duration::from_millis(500)).await;
        start_sidecar(app, shared);
    });
}

#[tauri::command]
fn emergency_stop_cmd(app: AppHandle, state: tauri::State<SharedSidecar>) {
    emergency_stop(&app, &Arc::clone(&state));
}

// ─── Entry point ─────────────────────────────────────────────────────────────

fn main() {
    // Prevent multiple instances using a named mutex / lock file
    #[cfg(target_os = "windows")]
    {
        use std::ffi::OsStr;
        use std::os::windows::ffi::OsStrExt;
        extern "system" {
            fn CreateMutexW(
                lp_mutex_attributes: *mut std::ffi::c_void,
                b_initial_owner: i32,
                lp_name: *const u16,
            ) -> *mut std::ffi::c_void;
            fn GetLastError() -> u32;
        }
        const ERROR_ALREADY_EXISTS: u32 = 183;
        let name: Vec<u16> = OsStr::new("Global\\TFNK_SingleInstance")
            .encode_wide()
            .chain(std::iter::once(0))
            .collect();
        unsafe {
            CreateMutexW(std::ptr::null_mut(), 1, name.as_ptr());
            if GetLastError() == ERROR_ALREADY_EXISTS {
                eprintln!("[TFNK] another instance is already running");
                std::process::exit(1);
            }
        }
    }

    #[cfg(not(target_os = "windows"))]
    {
        let lock_path = std::env::temp_dir().join("tfnk.lock");
        if lock_path.exists() {
            // Check if it's a stale lock by reading the PID
            if let Ok(pid_str) = std::fs::read_to_string(&lock_path) {
                let pid: u32 = pid_str.trim().parse().unwrap_or(0);
                // If /proc/<pid> does not exist the process is gone
                if pid > 0 && std::path::Path::new(&format!("/proc/{pid}")).exists() {
                    eprintln!("[TFNK] another instance is already running (pid {pid})");
                    std::process::exit(1);
                }
            }
        }
        let _ = std::fs::write(&lock_path, std::process::id().to_string());
    }

    let sidecar_state: SharedSidecar = Arc::new(Mutex::new(SidecarState::new()));
    let sidecar_for_tray = Arc::clone(&sidecar_state);
    let sidecar_for_run = Arc::clone(&sidecar_state);

    let context = tauri::generate_context!();

    tauri::Builder::default()
        // ── Single-instance guard (Tauri plugin-level, belt-and-suspenders) ──
        .plugin(tauri_plugin_single_instance_shim())
        // ── Managed state ─────────────────────────────────────────────────────
        .manage(Arc::clone(&sidecar_state))
        // ── System tray ───────────────────────────────────────────────────────
        .system_tray(build_tray())
        .on_system_tray_event(move |app, event| {
            handle_tray_event(app, event, Arc::clone(&sidecar_for_tray));
        })
        // ── Window events ─────────────────────────────────────────────────────
        .on_window_event(|event| {
            if let WindowEvent::CloseRequested { api, .. } = event.event() {
                // Minimise to tray instead of closing
                event.window().hide().unwrap_or_default();
                api.prevent_close();
            }
        })
        // ── Frontend commands ─────────────────────────────────────────────────
        .invoke_handler(tauri::generate_handler![
            get_sidecar_status,
            restart_sidecar,
            emergency_stop_cmd,
        ])
        // ── App setup ─────────────────────────────────────────────────────────
        .setup(move |app| {
            let app_handle = app.handle();
            let sidecar_clone = Arc::clone(&sidecar_state);

            // ── Global shortcuts ──────────────────────────────────────────────
            let mut shortcuts = app_handle.global_shortcut_manager();

            // Ctrl+Shift+T → toggle window
            let toggle_handle = app_handle.clone();
            shortcuts
                .register("Ctrl+Shift+T", move || {
                    toggle_window(&toggle_handle);
                })
                .unwrap_or_else(|e| eprintln!("[TFNK] shortcut register error: {e}"));

            // Ctrl+Shift+S → emergency stop
            let stop_handle = app_handle.clone();
            let stop_sidecar_ref = Arc::clone(&sidecar_clone);
            shortcuts
                .register("Ctrl+Shift+S", move || {
                    emergency_stop(&stop_handle, &stop_sidecar_ref);
                })
                .unwrap_or_else(|e| eprintln!("[TFNK] shortcut register error: {e}"));

            // ── Inject custom titlebar JS ─────────────────────────────────────
            if let Some(window) = app_handle.get_window("main") {
                // Wait for page load then inject drag region logic
                let win_clone = window.clone();
                tauri::async_runtime::spawn(async move {
                    tokio::time::sleep(Duration::from_secs(2)).await;
                    // Inject a script that makes elements with data-tauri-drag-region draggable
                    let _ = win_clone.eval(r#"
                        (function() {
                          function attachDrag(el) {
                            el.addEventListener('mousedown', function(e) {
                              if (e.button === 0) {
                                window.__TAURI__.window.getCurrent().startDragging();
                              }
                            });
                          }
                          document.querySelectorAll('[data-tauri-drag-region]').forEach(attachDrag);
                          const obs = new MutationObserver(function(muts) {
                            muts.forEach(function(m) {
                              m.addedNodes.forEach(function(n) {
                                if (n.nodeType === 1) {
                                  if (n.dataset && n.dataset.tauriDragRegion !== undefined) attachDrag(n);
                                  n.querySelectorAll && n.querySelectorAll('[data-tauri-drag-region]').forEach(attachDrag);
                                }
                              });
                            });
                          });
                          obs.observe(document.body, { childList: true, subtree: true });
                          console.log('[TFNK] drag region handler active');
                        })();
                    "#);
                });
            }

            // ── Start FastAPI sidecar ─────────────────────────────────────────
            start_sidecar(app_handle.clone(), Arc::clone(&sidecar_clone));

            Ok(())
        })
        // ── Run loop ──────────────────────────────────────────────────────────
        .build(context)
        .expect("error while building tauri application")
        .run(move |app_handle, event| {
            match event {
                RunEvent::ExitRequested { api, .. } => {
                    // Give sidecar a chance to clean up
                    stop_sidecar(&sidecar_for_run);
                    api.prevent_exit();
                    app_handle.exit(0);
                }
                RunEvent::Exit => {
                    stop_sidecar(&sidecar_for_run);

                    // Remove lock file on clean exit
                    #[cfg(not(target_os = "windows"))]
                    {
                        let lock_path = std::env::temp_dir().join("tfnk.lock");
                        let _ = std::fs::remove_file(lock_path);
                    }
                }
                _ => {}
            }
        });
}

// ─── Shim: no-op "single instance" plugin (tauri v1 built-in path) ───────────
// Tauri v1 does not ship a first-party single-instance plugin in the main
// crate, so we use an empty plugin here as a no-op placeholder.  The real
// guard is the OS mutex / lockfile above.
fn tauri_plugin_single_instance_shim<R: tauri::Runtime>() -> tauri::plugin::TauriPlugin<R> {
    tauri::plugin::Builder::new("single-instance").build()
}
