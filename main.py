from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.clock import Clock
from kivy.utils import platform
from kivy.core.window import Window
import math

Window.clearcolor = (0.04, 0.07, 0.13, 1)

# Android kutubxonalari
if platform == 'android':
    from jnius import autoclass, PythonJavaClass, java_method
    from android.permissions import request_permissions, Permission
    from android import activity

    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Context = autoclass('android.content.Context')
    SensorManager = autoclass('android.hardware.SensorManager')
    Sensor = autoclass('android.hardware.Sensor')
    BluetoothAdapter = autoclass('android.bluetooth.BluetoothAdapter')
    WifiManager = autoclass('android.net.wifi.WifiManager')
    ToneGenerator = autoclass('android.media.ToneGenerator')
    AudioManager = autoclass('android.media.AudioManager')
    Vibrator = autoclass('android.os.Vibrator')


class DetectorUI(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', padding=15, spacing=12, **kwargs)
        self.baseline_mag = None
        self.current_mag = 0.0
        self.devices = {}

        # Sarlavha
        self.add_widget(Label(
            text="[b]🛡️ MAKTAB TELEFON DETEKTORI[/b]",
            markup=True, font_size='22sp', size_hint_y=None, height=45, color=(0.22, 0.74, 0.97, 1)
        ))

        # 1-BO'LIM: CHO'NTAK DETEKTORI (MAGNITOMETR)
        self.mag_box = BoxLayout(orientation='vertical', padding=12, spacing=6, size_hint_y=None, height=180)
        self.mag_status = Label(
            text="🧲 CHO'NTAK SKANERI: TAYYOR",
            font_size='18sp', bold=True, color=(0.06, 0.73, 0.51, 1)
        )
        self.mag_value = Label(
            text="Magnit maydon: 0.0 µT",
            font_size='16sp', color=(0.8, 0.85, 0.9, 1)
        )
        self.cal_btn = Button(
            text="🎯 Fonni Nolga Tushirish (Kalibrlash)",
            size_hint_y=None, height=45,
            background_color=(0.23, 0.51, 0.96, 1), bold=True
        )
        self.cal_btn.bind(on_press=self.calibrate_sensor)

        self.mag_box.add_widget(self.mag_status)
        self.mag_box.add_widget(self.mag_value)
        self.mag_box.add_widget(self.cal_btn)
        self.add_widget(self.mag_box)

        # 2-BO'LIM: SINF RADARI (BLUETOOTH + WI-FI)
        self.scan_btn = Button(
            text="📡 SINF RADARINI ISHGA TUSHIRISH (BT / Wi-Fi)",
            size_hint_y=None, height=52,
            background_color=(0.55, 0.36, 0.96, 1), bold=True
        )
        self.scan_btn.bind(on_press=self.start_radar_scan)
        self.add_widget(self.scan_btn)

        self.radar_info = Label(
            text="Topilgan signallar ro'yxati:",
            size_hint_y=None, height=30, color=(0.6, 0.65, 0.75, 1)
        )
        self.add_widget(self.radar_info)

        self.scroll = ScrollView()
        self.list_layout = BoxLayout(orientation='vertical', size_hint_y=None, spacing=8)
        self.list_layout.bind(minimum_height=self.list_layout.setter('height'))
        self.scroll.add_widget(self.list_layout)
        self.add_widget(self.scroll)

        if platform == 'android':
            self.init_android()
        else:
            self.mag_value.text = "Kompyuter rejimi (Sensorlar Android telefonda ishlaydi)"

    def init_android(self):
        request_permissions([
            Permission.ACCESS_FINE_LOCATION,
            Permission.ACCESS_COARSE_LOCATION,
            Permission.BLUETOOTH_SCAN,
            Permission.BLUETOOTH_CONNECT,
            Permission.VIBRATE
        ])
        activity_ctx = PythonActivity.mActivity
        self.vibrator = activity_ctx.getSystemService(Context.VIBRATOR_SERVICE)
        self.tone = ToneGenerator(AudioManager.STREAM_ALARM, 90)
        self.wifi_manager = activity_ctx.getSystemService(Context.WIFI_SERVICE)
        self.bt_adapter = BluetoothAdapter.getDefaultAdapter()

        # Magnitometr sensorini ulash
        try:
            from plyer import compass
            compass.enable()
            Clock.schedule_interval(self.read_magnetometer, 0.25)
        except Exception as e:
            self.mag_value.text = f"Sensor xatosi: {e}"

    def calibrate_sensor(self, instance):
        self.baseline_mag = self.current_mag
        self.mag_status.text = "🟢 FON SOZLANDI — CHO'NTAKKA YAQINLASHTIRING"
        self.mag_status.color = (0.06, 0.73, 0.51, 1)

    def read_magnetometer(self, dt):
        try:
            from plyer import compass
            val = compass.field
            if val and val[0] is not None:
                mag = math.sqrt(val[0]**2 + val[1]**2 + val[2]**2)
                self.current_mag = mag
                if self.baseline_mag is None:
                    self.baseline_mag = mag

                diff = abs(mag - self.baseline_mag)
                self.mag_value.text = f"Ko'rsatkich: {mag:.1f} µT (Farq: +{diff:.1f} µT)"

                # Agar magnit farqi 25 µT dan oshsa — yaqinida telefon/metall bor!
                if diff > 25.0:
                    self.mag_status.text = "🔴 DIQQAT! TELEFON / METALL ANIQLANDI!"
                    self.mag_status.color = (0.94, 0.27, 0.27, 1)
                    if platform == 'android':
                        self.vibrator.vibrate(200)
                        self.tone.startTone(ToneGenerator.TONE_PROP_BEEP, 150)
                else:
                    self.mag_status.text = "🟢 TOZA (Telefon sezilmadi)"
                    self.mag_status.color = (0.06, 0.73, 0.51, 1)
        except Exception:
            pass

    def start_radar_scan(self, instance):
        self.list_layout.clear_widgets()
        if platform != 'android':
            self.add_device_card("Demo Telefon (Redmi Note)", -48, "Bluetooth")
            return

        # 1. Wi-Fi Hotspot / tarmoqlarni tekshirish
        try:
            self.wifi_manager.startScan()
            results = self.wifi_manager.getScanResults()
            for i in range(results.size()):
                res = results.get(i)
                ssid = res.SSID if res.SSID else "Yashirin Hotspot"
                rssi = res.level
                if rssi > -75:  # Faqat sinf ichidagi yaqin signallar
                    self.add_device_card(f"Wi-Fi/Hotspot: {ssid}", rssi, "Wi-Fi")
        except Exception as e:
            self.add_device_card(f"Wi-Fi ruxsati kerak: {e}", -90, "Xato")

        # 2. Ulangan/ko'ringan Bluetooth qurilmalarni tekshirish
        try:
            if self.bt_adapter and self.bt_adapter.isEnabled():
                bonded = self.bt_adapter.getBondedDevices().toArray()
                for dev in bonded:
                    self.add_device_card(f"BT Qurilma: {dev.getName()}", -55, "Bluetooth")
                self.bt_adapter.startDiscovery()
            else:
                self.add_device_card("Telefoningizda Bluetooth'ni yoqing!", -85, "Eslatma")
        except Exception:
            pass

    def add_device_card(self, name, rssi, kind):
        if rssi >= -55:
            status = "🔴 JUDA YAQIN (1-2 metr)"
            col = (0.94, 0.27, 0.27, 1)
        elif rssi >= -70:
            status = "🟡 SINF ICHIDA (3-6 metr)"
            col = (0.98, 0.8, 0.08, 1)
        else:
            status = "🟢 UZOQROQ"
            col = (0.06, 0.73, 0.51, 1)

        lbl = Label(
            text=f"[b]{name}[/b]\n{status} ({rssi} dBm)",
            markup=True, size_hint_y=None, height=60, color=col, halign='left'
        )
        self.list_layout.add_widget(lbl)


class TelefonDetektorApp(App):
    def build(self):
        return DetectorUI()


if __name__ == '__main__':
    TelefonDetektorApp().run()