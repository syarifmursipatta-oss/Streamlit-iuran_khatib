import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime, date
import plotly.express as px
from twilio.rest import Client
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Twilio setup
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN) if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN else None

# Fungsi untuk koneksi DB
@st.cache_resource
def init_db():
    conn = sqlite3.connect('iuran_khatib.db')
    c = conn.cursor()
    # Tabel jadwal
    c.execute('''
        CREATE TABLE IF NOT EXISTS jadwal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_khatib TEXT NOT NULL,
            tanggal DATE NOT NULL,
            terlaksana BOOLEAN DEFAULT FALSE,
            dibayar BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Tabel khatib (untuk menyimpan nomor WhatsApp)
    c.execute('''
        CREATE TABLE IF NOT EXISTS khatibs (
            nama_khatib TEXT PRIMARY KEY,
            nomor_whatsapp TEXT NOT NULL
        )
    ''')
    conn.commit()
    return conn

# Inisialisasi DB
conn = init_db()

# Fungsi untuk kirim notifikasi WhatsApp
def send_whatsapp_notification(nomor_whatsapp, message):
    if twilio_client and nomor_whatsapp:
        try:
            twilio_client.messages.create(
                body=message,
                from_=TWILIO_PHONE_NUMBER,
                to=f"whatsapp:{nomor_whatsapp}"
            )
            return True
        except Exception as e:
            st.error(f"Gagal mengirim notifikasi WhatsApp: {e}")
            return False
    return False

# Fungsi untuk load data
def load_data():
    df = pd.read_sql_query("SELECT * FROM jadwal ORDER BY tanggal DESC", conn)
    df['tanggal'] = pd.to_datetime(df['tanggal'])
    return df

# Fungsi untuk load data khatib
def load_khatibs():
    return pd.read_sql_query("SELECT * FROM khatibs", conn)

# Fungsi hitung tagihan (Rp 5.000 per jadwal)
def hitung_tagihan(df_khatib):
    total_jadwal = len(df_khatib)
    total_dibayar = len(df_khatib[df_khatib['dibayar'] == True])
    tagihan = total_jadwal * 5000
    sudah_bayar = total_dibayar * 5000
    belum_bayar = tagihan - sudah_bayar
    return total_jadwal, total_dibayar, tagihan, sudah_bayar, belum_bayar

# UI Aplikasi
st.set_page_config(page_title="Iuran Khatib Jumat", layout="wide")

# Logo aplikasi
st.image("https://via.placeholder.com/150x50.png?text=Masjid+Logo", width=150)  # Ganti dengan path logo Anda
st.title("📅 Aplikasi Pencatatan Iuran Khatib Jumat")
st.markdown("Setiap jadwal: **Rp 5.000**. Update status terlaksana & pembayaran untuk rekap akurat.")

# Sidebar untuk navigasi
page = st.sidebar.selectbox("Pilih Halaman:", ["Input Jadwal Baru", "Daftar Jadwal", "Frekuensi Jadwal", "Tagihan Iuran", "Rekap per Khatib", "Manajemen Khatib"])

if page == "Manajemen Khatib":
    st.header("Manajemen Data Khatib")
    with st.form("input_khatib"):
        nama_khatib = st.text_input("Nama Khatib")
        nomor_whatsapp = st.text_input("Nomor WhatsApp (format: +628123456789)")
        submitted = st.form_submit_button("Tambah Khatib")
        if submitted and nama_khatib and nomor_whatsapp:
            c = conn.cursor()
            try:
                c.execute("INSERT INTO khatibs (nama_khatib, nomor_whatsapp) VALUES (?, ?)", (nama_khatib, nomor_whatsapp))
                conn.commit()
                st.success(f"Khatib {nama_khatib} ditambahkan!")
            except sqlite3.IntegrityError:
                st.error("Nama khatib sudah ada!")
    st.subheader("Daftar Khatib")
    df_khatibs = load_khatibs()
    if not df_khatibs.empty:
        st.dataframe(df_khatibs)
    else:
        st.info("Belum ada data khatib.")

elif page == "Input Jadwal Baru":
    st.header("Tambah Jadwal Baru")
    df_khatibs = load_khatibs()
    khatib_options = df_khatibs['nama_khatib'].tolist() if not df_khatibs.empty else []
    with st.form("input_jadwal"):
        nama_khatib = st.selectbox("Nama Khatib", options=khatib_options)
        tanggal = st.date_input("Tanggal Jumat", value=date.today())
        submitted = st.form_submit_button("Tambah Jadwal")
        if submitted and nama_khatib:
            c = conn.cursor()
            c.execute("INSERT INTO jadwal (nama_khatib, tanggal) VALUES (?, ?)", (nama_khatib, tanggal))
            conn.commit()
            st.success(f"Jadwal untuk {nama_khatib} pada {tanggal} ditambahkan!")
            # Kirim notifikasi WhatsApp
            nomor = df_khatibs[df_khatibs['nama_khatib'] == nama_khatib]['nomor_whatsapp'].iloc[0]
            message = f"Jadwal khutbah Anda pada {tanggal} ditambahkan!"
            if send_whatsapp_notification(nomor, message):
                st.info(f"Notifikasi WhatsApp dikirim ke {nama_khatib}!")
            else:
                st.warning("Notifikasi WhatsApp gagal dikirim. Cek konfigurasi Twilio.")

elif page == "Daftar Jadwal":
    st.header("Daftar Semua Jadwal")
    df = load_data()
    df_khatibs = load_khatibs()
    if not df.empty:
        for idx, row in df.iterrows():
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.write(f"**{row['nama_khatib']}** - {row['tanggal'].date()}")
            with col2:
                terlaksana = st.checkbox("Terlaksana", value=row['terlaksana'], key=f"terlaksana_{row['id']}")
            with col3:
                dibayar = st.checkbox("Dibayar", value=row['dibayar'], key=f"dibayar_{row['id']}")
            with col4:
                if st.button("Update", key=f"update_{row['id']}"):
                    c = conn.cursor()
                    c.execute("UPDATE jadwal SET terlaksana=?, dibayar=? WHERE id=?", (terlaksana, dibayar, row['id']))
                    conn.commit()
                    # Kirim notifikasi WhatsApp jika status pembayaran berubah
                    if row['dibayar'] != dibayar:
                        nomor = df_khatibs[df_khatibs['nama_khatib'] == row['nama_khatib']]['nomor_whatsapp'].iloc[0]
                        status = "Lunas" if dibayar else "Belum Dibayar"
                        message = f"Pembayaran iuran untuk {row['tanggal'].date()} telah diperbarui: {status}."
                        if send_whatsapp_notification(nomor, message):
                            st.info(f"Notifikasi WhatsApp dikirim ke {row['nama_khatib']}!")
                        else:
                            st.warning("Notifikasi WhatsApp gagal dikirim.")
                    st.rerun()
        st.dataframe(df)
    else:
        st.info("Belum ada jadwal. Tambahkan di halaman Input!")

elif page == "Frekuensi Jadwal":
    st.header("Frekuensi Jadwal Terlaksana")
    df = load_data()
    if not df.empty:
        freq_terlaksana = df[df['terlaksana'] == True].groupby('nama_khatib').size().reset_index(name='Jumlah Terlaksana')
        freq_total = df.groupby('nama_khatib').size().reset_index(name='Total Jadwal')
        freq = pd.merge(freq_total, freq_terlaksana, on='nama_khatib', how='left').fillna(0)
        st.dataframe(freq)
        fig = px.bar(freq, x='nama_khatib', y=['Total Jadwal', 'Jumlah Terlaksana'], barmode='group', title="Frekuensi per Khatib")
        st.plotly_chart(fig)
    else:
        st.info("Belum ada data jadwal.")

elif page == "Tagihan Iuran":
    st.header("Tagihan Iuran Keseluruhan")
    df = load_data()
    if not df.empty:
        total_jadwal, total_dibayar, total_tagihan, total_sudah_bayar, total_belum_bayar = hitung_tagihan(df)
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Jadwal", total_jadwal)
        with col2:
            st.metric("Sudah Dibayar", f"Rp {total_sudah_bayar:,}", delta=f"Rp {total_belum_bayar:,}")
        with col3:
            st.metric("Belum Dibayar", f"Rp {total_belum_bayar:,}")
        df_display = df.copy()
        df_display['Tagihan'] = 5000
        df_display['Status Bayar'] = df_display['dibayar'].map({True: 'Lunas', False: 'Belum'})
        st.dataframe(df_display[['nama_khatib', 'tanggal', 'terlaksana', 'Status Bayar', 'Tagihan']])
    else:
        st.info("Belum ada data.")

elif page == "Rekap per Khatib":
    st.header("Rekap Iuran per Khatib")
    khatib_pilih = st.selectbox("Pilih Khatib:", options=load_data()['nama_khatib'].unique() if not load_data().empty else [])
    if khatib_pilih:
        df_khatib = load_data()[load_data()['nama_khatib'] == khatib_pilih]
        total_jadwal, total_dibayar, tagihan, sudah_bayar, belum_bayar = hitung_tagihan(df_khatib)
        st.subheader(f"Rekap {khatib_pilih}")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Jadwal", total_jadwal)
        with col2:
            st.metric("Terlaksana", total_dibayar)
        with col3:
            st.metric("Sudah Bayar", f"Rp {sudah_bayar:,}")
        with col4:
            st.metric("Tagihan", f"Rp {tagihan:,}", delta=f"- Rp {sudah_bayar:,}")
        st.subheader("Detail Jadwal")
        st.dataframe(df_khatib)
    else:
        st.info("Pilih khatib untuk rekap.")

# Footer
st.markdown("---")
st.caption("Aplikasi sederhana oleh Grok. Hubungi jika butuh modifikasi (misal: login atau export Excel).")