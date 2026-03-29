use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Serialize, Deserialize, Clone)]
pub struct AppConfig {
    pub api_url: String,
    pub api_key: String,
}

#[derive(Serialize)]
pub struct FirstRunResult {
    pub first_run: bool,
}

fn config_dir() -> PathBuf {
    let home = dirs::home_dir().expect("Cannot determine home directory");
    #[cfg(feature = "omnius")]
    {
        home.join(".omnius")
    }
    #[cfg(not(feature = "omnius"))]
    {
        home.join(".gilbertus")
    }
}

fn config_path() -> PathBuf {
    config_dir().join("config.json")
}

#[tauri::command]
pub fn check_first_run() -> FirstRunResult {
    let path = config_path();
    FirstRunResult {
        first_run: !path.exists(),
    }
}

#[tauri::command]
pub fn save_config(api_url: String, api_key: String) -> Result<(), String> {
    let dir = config_dir();
    std::fs::create_dir_all(&dir).map_err(|e| format!("Cannot create config dir: {}", e))?;

    let config = AppConfig { api_url, api_key };
    let json =
        serde_json::to_string_pretty(&config).map_err(|e| format!("Serialization error: {}", e))?;

    std::fs::write(config_path(), json).map_err(|e| format!("Cannot write config: {}", e))?;

    Ok(())
}

#[tauri::command]
pub fn get_config() -> Result<AppConfig, String> {
    let path = config_path();
    let data = std::fs::read_to_string(&path)
        .map_err(|e| format!("Cannot read config at {}: {}", path.display(), e))?;

    let config: AppConfig =
        serde_json::from_str(&data).map_err(|e| format!("Invalid config JSON: {}", e))?;

    Ok(config)
}
