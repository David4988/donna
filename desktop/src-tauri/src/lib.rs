//! DONNA's Rust layer stays thin: window and one command that tells the UI where
//! the Python core is. No agent logic lives here.
//!
//! Later: tray, global push-to-talk hotkey, and spawning the core as a sidecar.

use std::path::PathBuf;

use serde::{Deserialize, Serialize};
use tauri::Manager;

/// What the UI needs to connect. Read from the session file the core writes.
#[derive(Debug, Deserialize, Serialize, PartialEq)]
struct CoreSession {
    port: u16,
    token: String,
}

fn session_file(home: PathBuf) -> PathBuf {
    match std::env::var_os("DONNA_HOME") {
        Some(dir) => PathBuf::from(dir).join("session.json"),
        None => home.join(".donna").join("session.json"),
    }
}

fn parse_session(contents: &str) -> Result<CoreSession, String> {
    serde_json::from_str(contents).map_err(|e| format!("invalid session file: {e}"))
}

#[tauri::command]
fn core_session(app: tauri::AppHandle) -> Result<CoreSession, String> {
    let home = app.path().home_dir().map_err(|e| e.to_string())?;
    let path = session_file(home);
    let contents = std::fs::read_to_string(&path)
        .map_err(|e| format!("core not running ({}): {e}", path.display()))?;
    parse_session(&contents)
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![core_session])
        .run(tauri::generate_context!())
        .expect("error while running DONNA");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_session_file_and_ignores_extra_fields() {
        let s = parse_session(r#"{"port": 4321, "token": "abc", "pid": 99}"#).unwrap();
        assert_eq!(
            s,
            CoreSession {
                port: 4321,
                token: "abc".into()
            }
        );
    }

    #[test]
    fn rejects_garbage() {
        assert!(parse_session("not json").is_err());
        assert!(parse_session(r#"{"port": 99999, "token": "x"}"#).is_err());
    }
}
