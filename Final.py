
import googlemaps
import pandas as pd
import time
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import os

# === Нежелательные ключевые слова (в нижнем регистре) ===
blacklist = [
    "копицентр", "печать", "типография", "ultraprint",
    "аптека", "кафе", "парикмахерская", "принтер", "notary", "нотариус"
]


# === Список областей Украины ===
ukrainian_regions = [
   "Винницкая", "Волынская", "Днепропетровская", "Донецкая", "Житомирская", "Закарпатская",
   "Запорожская", "Ивано-франковская", "Киевская", "Кировоградская", "Луганская",
   "Львовская", "Николаевская", "Одесская", "Полтавская", "Ровенская", "Сумская",
   "Тернопольская", "Харьковская", "Херсонская", "Хмельницкая", "Черкасская",
   "Черниговская", "Черновицкая"
]


# === Загрузка API ключа из текстового файла ===
def load_api_key(filename="apikey.txt"):
    try:
        with open(filename, "r") as file:
            return file.read().strip()
    except Exception as e:
        messagebox.showerror("Ошибка", f"Не удалось загрузить API ключ:\n{e}")
        return None


# === Безопасное сохранение ===
def save_dataframe_safely(df, filename_base):
    name, ext = os.path.splitext(filename_base)
    i = 1
    filename = filename_base
    while True:
        try:
            df.to_excel(filename, index=False)
            return filename
        except PermissionError:
            filename = f"{name} ({i}){ext}"
            i += 1


# === Подготовка данных ===
def setting_strings():

    full_input = label_value.cget("text")
    main_input = entry.get().strip()
    user_input = entry_alter.get().strip()
    isCorrect = False

    query=""
    first, second = modify_main_input(full_input, f"{region_combobox.get()}")
    region = region_combobox.get()

    if first == "СТО в":
        city, detail = modify_main_input(main_input, ",")
        file = f"СТО {region}_{city}_{detail}.xlsx"
        geocode_query = f"{city}, {region}, Украина"

        if detail:
            query = f"СТО в {region} {city} {detail}"
            isCorrect = True


        return geocode_query, query, file, isCorrect

    else:
        query = user_input
        isCorrect = True
        file = f"{query}.xlsx"
        geocode_query = f"{region}, Украина"
        return geocode_query, query, file, isCorrect

def modify_main_input(main_text, middler):
    parts = [p.strip() for p in main_text.split(middler)]
    if len(parts) >= 2:
        city = f"{middler} ".join(parts[:-1])  # всё до последней части
        detail = parts[-1]
    else:
        detail = ""
        city = parts[0] if parts else ""
    return city, detail


# === Открытия папки с файлом ===
def open_fileway(filename):
    # Если флажок активен — открыть проводник с файлом
    if show_way.get():
        try:
            abs_path = os.path.abspath(filename)
            os.startfile(os.path.dirname(abs_path))  # Открыть папку с файлом
        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось открыть проводник:\n{e}")


# === Алгоритм поиска ===
def start_search():
    thread = threading.Thread(target=search_places)
    thread.start()

def search_places():

    location_query, query, filename, isGood = setting_strings()

    if not isGood:
        messagebox.showerror("Ошибка", "Не корректный вид строки")
        return

    proceed = messagebox.askokcancel("Подтверждение", f"Начать поиск {query}?")
    if not proceed:
        return

    all_places = []
    next_page_token = None

    try:

        # Геокодируем город
        geocode_result = gmaps.geocode(location_query)

        if not geocode_result:
            messagebox.showerror("Ошибка", "Не удалось определить координаты города/района")
            return

        location = geocode_result[0]['geometry']['location']
        latlng = (location['lat'], location['lng'])


        while True:
            if next_page_token:
                places = gmaps.places(query=query, location=latlng, page_token=next_page_token, language="ru")

            else:
                places = gmaps.places(query=query, location=latlng, language="ru")

            results = [place for place in places.get('results', []) if is_relevant_place(place)]

            for place in results:
                name = place.get('name')
                rating = place.get('rating')
                place_id = place['place_id']

                details = gmaps.place(place_id=place_id, language="ru")

                result = details.get('result', {})
                business_status = result.get("business_status", "UNKNOWN")

                location = result.get('geometry', {}).get('location', {})
                lat = location.get('lat')
                lng = location.get('lng')

                all_places.append({
                    "Название": name,
                    "Адрес": result.get('formatted_address', ''),
                    "Телефон": result.get('formatted_phone_number', ''),
                    "Сайт": result.get('website', ''),
                    "Рейтинг": rating,
                    "Ссылка на карту": f"https://www.google.com.ua/maps/place/{lat},{lng}",
                    "Широта": lat,
                    "Долгота":lng,
                    "Статус": (
                        "Работает" if business_status == "OPERATIONAL"
                        else "Временно закрыто" if business_status == "CLOSED_TEMPORARILY"
                        else "Закрыто навсегда" if business_status == "CLOSED_PERMANENTLY"
                        else "Неизвестно"
                    ),

                })

            next_page_token = places.get('next_page_token')
            if not next_page_token:
                break
            else:
                time.sleep(2)

        if all_places:
            df = pd.DataFrame(all_places)
            saved_filename = save_dataframe_safely(df, filename)

            messagebox.showinfo("Готово", f"Найдено {len(all_places)} СТО.\nСохранено в файл:\n{saved_filename}")

            open_fileway(saved_filename)


        else:
            messagebox.showinfo("Результат", "СТО не найдены.")

    except Exception as e:
        messagebox.showerror("Ошибка", f"Что-то пошло не так:\n{e}")

def is_relevant_place(place):
    name = place.get("name", "").lower()
    types = [t.lower() for t in place.get("types", [])]

    # Проверка по имени и типам
    for bad_word in blacklist:
        if bad_word in name:
            return False
        if any(bad_word in t for t in types):
            return False

    return True

# 🔑 Твой ключ API
API_KEY = load_api_key()
if API_KEY is None:
    exit()  # Если не удалось загрузить ключ, программа завершится
gmaps = googlemaps.Client(key=API_KEY)



# 🎨 Интерфейс

# === Активное поле и подсказки ===
def set_placeholder(entry_widget, placeholder_text):
    entry_widget.insert(0, placeholder_text)
    entry_widget.config(fg='grey')
main_placeholder_active = True
alt_placeholder_active = True
last = "main"

# === Обработчики событий действий с полями ввода ===
def on_main_entry_click(event):
    global last, main_placeholder_active
    last = "main"
    if main_placeholder_active:
        entry.delete(0, tk.END)
        entry.config(fg='black')
        main_placeholder_active = False

    entry_alter.unbind("<KeyRelease>")
    label_value.config(text = f"СТО в {region_combobox.get()} {entry.get().strip()}")
    entry.bind("<KeyRelease>", on_main_typing)

def select_region(event):
    global last
    match last:
        case "main":
            label_value.config(text=f"СТО в {region_combobox.get()} {entry.get().strip()}")
        case "alter":
            label_value.config(text=f"{region_combobox.get()} {entry_alter.get().strip()}")

def on_alt_entry_click(event):
    global last, alt_placeholder_active
    last = "alter"
    if alt_placeholder_active:
        entry_alter.delete(0, tk.END)
        entry_alter.config(fg='black')
        alt_placeholder_active = False

    entry.unbind("<KeyRelease>")
    label_value.config(text = f"{region_combobox.get()} {entry_alter.get().strip()}")
    entry_alter.bind("<KeyRelease>", on_alt_typing)

def on_main_typing(event):
    label_value.config(text=f"СТО в {region_combobox.get()} {entry.get().strip()}")

def on_alt_typing(event):
    label_value.config(text=f"{region_combobox.get()} {entry_alter.get().strip()}")


# === Окно ===

root = tk.Tk()
root.title("Поиск СТО в регионе")
root.geometry("500x420")
root.minsize(500, 420)


# === Основной блок ===

first_frame = tk.LabelFrame(
    root,
    text="1 Выбор области",
    font=("Arial", 10, "bold"))
first_frame.pack(
    padx=50,
    pady=5,
    fill="both")

selected_region = tk.StringVar()
region_combobox = ttk.Combobox(
    first_frame,
    textvariable=selected_region,
    values=ukrainian_regions,
    font=("Arial", 12),
    width=35,
    state="readonly")
region_combobox.current(0)
region_combobox.pack(
    pady=(10,20),
    padx=10
)

second_frame = tk.LabelFrame(
    root,
    text="2 Выбор города и района",
    font=("Arial", 10, "bold"))
second_frame.pack(
    padx=50,
    pady=(28,0),
    fill="both")

entry = tk.Entry(
    second_frame,
    font=("Arial", 12),
    width=37)
entry.pack(pady=(10,20))

ENTRY_MAIN_PLACEHOLDER = "Винница, Замостянский район"
set_placeholder(entry, ENTRY_MAIN_PLACEHOLDER)


# === Альтернативный блок ===

alt_frame = tk.LabelFrame(
    root,
    text="Альтернативний поиск",
    font=("Arial", 10, "bold"))
alt_frame.pack(
    padx=50,
    pady=10,
    fill="both")

entry_alter = tk.Entry(
    alt_frame,
    font=("Arial", 12),
    width=37)
entry_alter.pack(pady=(10,20))

ENTRY_ALTER_PLACEHOLDER = "Автосервис Винница Винницкие хутора"
set_placeholder(entry_alter, ENTRY_ALTER_PLACEHOLDER)


# === Текущая сторка поиска ===

label_name = tk.Label(
    root,
    text="Поисковая строка:",
    font=("Arial", 10, "bold"))
label_name.pack(
    anchor="w",
    padx=(48,0))

label_value = tk.Label(
    root,
    text = f"СТО в {region_combobox.get()} {ENTRY_MAIN_PLACEHOLDER}",
    font=("Arial", 10,))
label_value.pack(
    anchor="w",
    padx=(48,0))


entry.bind("<Button-1>", on_main_entry_click)
entry_alter.bind("<Button-1>", on_alt_entry_click)
region_combobox.bind("<<ComboboxSelected>>", select_region)


# === Кнопка поиска ===

search_button = tk.Button(
    root,
    text="Искать",
    font=("Arial", 12),
    width=8,
    bg="#E0E0E0",
    activebackground="#B3D9FF",
    command=start_search)
search_button.pack(pady=(10,0))


# === Чекбокс ===

show_way = tk.BooleanVar()
checkbox = tk.Checkbutton(
    root,
    text="Показывать файл результата",
    variable=show_way,
    font=("Arial", 10),
    anchor="w",
    justify="left"
)
checkbox.pack(
    side="bottom",
    anchor="sw",
    pady=(0,15),
    padx=(45,0))


# === Отображение окна = Запуск ===

root.mainloop()


