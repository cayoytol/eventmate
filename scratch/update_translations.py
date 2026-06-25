# scratch/update_translations.py
import json
import os

languages = {
    "en": {
        "nav_settings": "Settings",
        "settingsPage": {
            "title": "Profile Settings",
            "subtitle": "Manage your avatar, name, and interface language.",
            "avatarTitle": "Avatar",
            "avatarFormats": "Supported Formats: JPEG, PNG, WebP",
            "avatarMaxSize": "Max File Size: 5 MB",
            "uploadAvatar": "Upload Avatar",
            "uploadingAvatar": "Uploading Avatar...",
            "generalSettings": "General Settings",
            "username": "Username",
            "emailReadonly": "Email Address (Read-only)",
            "interfaceLanguage": "Interface Language",
            "saveSettings": "Save Settings",
            "saving": "Saving...",
            "profileUpdated": "Profile settings updated successfully.",
            "avatarUpdated": "Avatar updated successfully.",
            "updateFailed": "Failed to update settings.",
            "invalidFileType": "Invalid file type. Only JPEG, PNG, and WebP are supported.",
            "fileTooLarge": "File too large. Maximum size is 5 MB."
        }
    },
    "ru": {
        "nav_settings": "Настройки",
        "settingsPage": {
            "title": "Настройки профиля",
            "subtitle": "Управляйте вашим аватаром, именем и языком интерфейса.",
            "avatarTitle": "Аватар",
            "avatarFormats": "Поддерживаемые форматы: JPEG, PNG, WebP",
            "avatarMaxSize": "Максимальный размер файла: 5 МБ",
            "uploadAvatar": "Загрузить аватар",
            "uploadingAvatar": "Загрузка аватара...",
            "generalSettings": "Общие настройки",
            "username": "Имя пользователя",
            "emailReadonly": "Email адрес (Только чтение)",
            "interfaceLanguage": "Язык интерфейса",
            "saveSettings": "Сохранить настройки",
            "saving": "Сохранение...",
            "profileUpdated": "Настройки профиля успешно сохранены.",
            "avatarUpdated": "Аватар успешно обновлен.",
            "updateFailed": "Не удалось обновить настройки.",
            "invalidFileType": "Неверный тип файла. Поддерживаются только JPEG, PNG и WebP.",
            "fileTooLarge": "Файл слишком большой. Максимальный размер 5 МБ."
        }
    },
    "kz": {
        "nav_settings": "Баптаулар",
        "settingsPage": {
            "title": "Профиль баптаулары",
            "subtitle": "Аватарыңызды, атыңызды және интерфейс тілін басқарыңыз.",
            "avatarTitle": "Аватар",
            "avatarFormats": "Қолдау көрсетілетін форматтар: JPEG, PNG, WebP",
            "avatarMaxSize": "Файлдың максималды өлшемі: 5 МБ",
            "uploadAvatar": "Аватарды жүктеу",
            "uploadingAvatar": "Аватар жүктелуде...",
            "generalSettings": "Жалпы баптаулар",
            "username": "Пайдаланушы аты",
            "emailReadonly": "Email мекенжайы (Тек оқу үшін)",
            "interfaceLanguage": "Интерфейс тілі",
            "saveSettings": "Баптауларды сақтау",
            "saving": "Сақталуда...",
            "profileUpdated": "Профиль баптаулары сәтті сақталды.",
            "avatarUpdated": "Аватар сәтті жаңартылды.",
            "updateFailed": "Баптауларды жаңарту сәтсіз аяқталды.",
            "invalidFileType": "Файл түрі қате. Тек JPEG, PNG және WebP форматтарына қолдау көрсетіледі.",
            "fileTooLarge": "Файл тым үлкен. Максималды өлшемі - 5 МБ."
        }
    }
}

base_dir = "c:/Users/void7/Downloads/eventmate-main/eventmate-main/frontend/messages"

for lang, data in languages.items():
    file_path = os.path.join(base_dir, f"{lang}.json")
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        continue
    
    with open(file_path, "r", encoding="utf-8") as f:
        json_data = json.load(f)
    
    # 1. Update nav settings
    if "nav" not in json_data:
        json_data["nav"] = {}
    json_data["nav"]["settings"] = data["nav_settings"]
    
    # 2. Update settingsPage
    json_data["settingsPage"] = data["settingsPage"]
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"Successfully updated translations for {lang}")
