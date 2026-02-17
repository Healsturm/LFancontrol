Linux Fan Control (PySide6)
===========================

Bu proje, Linux üzerinde `/sys/class/hwmon` arayüzünü kullanarak fan devirlerini gösteren
ve (donanım/izin destekliyorsa) PWM üzerinden manuel kontrol sağlayan basit bir
grafik arayüzlü fan kontrol uygulamasıdır.

Kurulum
-------

Gereksinimler:

- Python 3.9 veya üzeri
- Linux (hwmon/sysfs desteği olan bir çekirdek)

Gerekli Python bağımlılıklarını yüklemek için:

```bash
pip install -r requirements.txt
```

Kullanım
--------

Uygulamayı başlatmak için:

```bash
python app.py
```

veya aynı klasörde:

```bash
./run.sh
```

`run.sh` betiğini ilk kez kullanmadan önce çalıştırılabilir yapmanız gerekir:

```bash
chmod +x run.sh
```

Notlar:

- Normal kullanıcı olarak çalıştırdığınızda, genellikle **okuma (RPM)** mümkündür, ancak
  **PWM yazma** işlemleri için çoğu sistemde root izni gerekir.
- PWM değerini değiştirmek istediğinizde izin hatası alırsanız:
  - Uygulamayı `sudo python app.py` ile çalıştırmayı deneyebilir veya
  - İlgili fan PWM dosyalarına yazma izni veren uygun bir `udev`/`polkit` kuralı
    oluşturmayı düşünebilirsiniz.

Donanım Desteği
---------------

Uygulama, `/sys/class/hwmon/hwmonX` dizinleri altında:

- `fan*_input` dosyalarından RPM değerlerini okur,
- `pwm*` ve varsa `pwm*_enable` dosyaları üzerinden PWM kontrolü dener.

Eğer sisteminizde uygun `hwmon` sensörleri yoksa veya fan/pwm dosyaları
bulunamazsa, uygulama içinde bilgilendirici bir mesaj göreceksiniz.

Klasörden Tek Tıkla Çalıştırma
------------------------------

- `run.sh` dosyasını çalıştırılabilir yaptıktan sonra (`chmod +x run.sh`),
  çoğu dosya yöneticisinde bu dosyaya çift tıklayarak uygulamayı başlatabilirsiniz.
- Ayrıca `LinuxFanControl.desktop` dosyasını masaüstüne kopyalayıp
  çalıştırılabilir yaptığınızda, masaüstü üzerinden de tek tıkla açabilirsiniz.
  Gerekirse bu dosyanın içindeki `Path=` satırını projenizi taşıdığınız konuma göre
  güncelleyebilirsiniz.

