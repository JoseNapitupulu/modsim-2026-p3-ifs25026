import streamlit as st
import simpy
import random
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dataclasses import dataclass
from datetime import datetime, timedelta

# =========================================================
# CONFIG
# =========================================================

@dataclass
class Config:

    NUM_MEJA: int = 60
    MAHASISWA_PER_MEJA: int = 3

    PETUGAS_LAUK: int = 3
    PETUGAS_ANGKUT: int = 2
    PETUGAS_NASI: int = 2

    LAUK_MIN_TIME: float = 30
    LAUK_MAX_TIME: float = 60

    ANGKUT_MIN_TIME: float = 20
    ANGKUT_MAX_TIME: float = 60
    ANGKUT_MIN_LOAD: int = 4
    ANGKUT_MAX_LOAD: int = 7

    NASI_MIN_TIME: float = 30
    NASI_MAX_TIME: float = 60

    START_HOUR: int = 7
    START_MINUTE: int = 0

    RANDOM_SEED: int = 42

    @property
    def TOTAL_OMPRENG(self):
        return self.NUM_MEJA * self.MAHASISWA_PER_MEJA


# =========================================================
# MODEL SIMULASI
# =========================================================

class PiketOmprengDES:

    def __init__(self, config):
        self.config = config
        self.env = simpy.Environment()

        self.petugas_lauk = simpy.Resource(self.env, config.PETUGAS_LAUK)
        self.petugas_angkut = simpy.Resource(self.env, config.PETUGAS_ANGKUT)
        self.petugas_nasi = simpy.Resource(self.env, config.PETUGAS_NASI)

        self.antrian_lauk = simpy.Store(self.env)
        self.antrian_nasi = simpy.Store(self.env)

        self.data = []
        self.completed = 0

        self.busy_lauk = 0
        self.busy_angkut = 0
        self.busy_nasi = 0

        self.start_time = datetime(
            2024,1,1,
            config.START_HOUR,
            config.START_MINUTE
        )

        random.seed(config.RANDOM_SEED)
        np.random.seed(config.RANDOM_SEED)

    def waktu_ke_jam(self, detik):
        return self.start_time + timedelta(seconds=detik)

    def waktu_lauk(self):
        return random.uniform(self.config.LAUK_MIN_TIME,
                              self.config.LAUK_MAX_TIME)

    def waktu_angkut(self):
        return random.uniform(self.config.ANGKUT_MIN_TIME,
                              self.config.ANGKUT_MAX_TIME)

    def waktu_nasi(self):
        return random.uniform(self.config.NASI_MIN_TIME,
                              self.config.NASI_MAX_TIME)

    # ---------- LAUK ----------
    def proses_ompreng(self, oid):

        datang = self.env.now

        with self.petugas_lauk.request() as req:
            yield req
            mulai_lauk = self.env.now
            t = self.waktu_lauk()
            yield self.env.timeout(t)

        self.busy_lauk += t

        yield self.antrian_lauk.put({
            "id": oid,
            "datang": datang,
            "mulai_lauk": mulai_lauk,
            "selesai_lauk": self.env.now
        })
    

    # ---------- ANGKUT ----------
    def proses_angkut(self):

        while self.completed < self.config.TOTAL_OMPRENG:

            if len(self.antrian_lauk.items) == 0:
                yield self.env.timeout(0.5)
                continue

            batch = []
            kapasitas = random.randint(
                self.config.ANGKUT_MIN_LOAD,
                self.config.ANGKUT_MAX_LOAD
            )

            for _ in range(min(kapasitas,
                               len(self.antrian_lauk.items))):
                batch.append((yield self.antrian_lauk.get()))

            with self.petugas_angkut.request() as req:
                yield req
                t = self.waktu_angkut()
                yield self.env.timeout(t)

            self.busy_angkut += t

            for item in batch:
                item["selesai_angkut"] = self.env.now
                yield self.antrian_nasi.put(item)

    # ---------- NASI ----------
    def proses_nasi(self):

        while self.completed < self.config.TOTAL_OMPRENG:

            if len(self.antrian_nasi.items) == 0:
                yield self.env.timeout(0.5)
                continue

            item = yield self.antrian_nasi.get()

            with self.petugas_nasi.request() as req:
                yield req
                mulai_nasi = self.env.now
                t = self.waktu_nasi()
                yield self.env.timeout(t)

            self.busy_nasi += t
            selesai = self.env.now

            self.data.append({
                "id": item["id"],
                "mulai_lauk": item["mulai_lauk"],
                "selesai_lauk": item["selesai_lauk"],
                "mulai_nasi": mulai_nasi,
                "selesai_nasi": selesai,
                "total_waktu": selesai - item["datang"],
                "jam_selesai": self.waktu_ke_jam(selesai)
            })

            self.completed += 1

    def generate(self):
        for i in range(self.config.TOTAL_OMPRENG):
            self.env.process(self.proses_ompreng(i))
            yield self.env.timeout(0)

    # ---------- RUN ----------
    def run(self):

        self.env.process(self.generate())
        self.env.process(self.proses_angkut())
        self.env.process(self.proses_nasi())

        self.env.run()

        return self.analyze_results()

    # ---------- ANALISIS ----------
    def analyze_results(self):

        df = pd.DataFrame(self.data)

        total_time = df["total_waktu"].max()

        results = {
            "durasi_total_detik": total_time,
            "avg_total_time": df["total_waktu"].mean(),
            "total_ompreng": len(df)
        }

        return results, df



# =========================================================
# STREAMLIT UI
# =========================================================
st.set_page_config(
    page_title="Simulasi Kantin IT Del",
    page_icon="🍱",
    layout="wide"
)

# ============================
# SIDEBAR PARAMETER
# ============================
st.sidebar.markdown("""

                <style>
                                    

                /* box profile */
                .profile-box {
                    padding: 12px 16px;
                    border-radius: 10px;
                    background: #1f2937;
                    margin-top: 10px;
                    animation: glow 3s infinite alternate;
                }

                .profile-title {
                    font-size: 1rem;
                    font-weight: 600;
                    margin-bottom: 6px;
                }

                .profile-item {
                    font-size: 0.95rem;
                    margin: 2px 0;
                }

                /* link github */
                .profile-item a {
                    color: #3b82f6;
                    text-decoration: none;
                }

                .profile-item a:hover {
                    text-decoration: underline;
                }

                /* glow animation */
                @keyframes glow {
                    from { box-shadow: 0 0 5px rgba(59,130,246,0.4); }
                    to   { box-shadow: 0 0 14px rgba(59,130,246,0.8); }
                }

                </style>


                <div class="profile-box">
                    <div class="profile-title">👤 Profile</div>
                    <div class="profile-item">By:Jose Napitupulu</div>
                    <div class="profile-item">
                        <a href="https://github.com/JoseNapitupulu" target="_blank">GitHub</a>
                    </div>
                </div>
                """, unsafe_allow_html=True)

st.sidebar.title("⚙️ Parameter Simulasi")

# =====================
# PARAMETER SISTEM
# =====================
st.sidebar.markdown("### 👥 Parameter Sistem")

num_meja = st.sidebar.slider(
    "Jumlah Meja",
    min_value=10,
    max_value=120,
    value=60
)

mahasiswa_per_meja = st.sidebar.slider(
    "Mahasiswa per Meja",
    min_value=1,
    max_value=6,
    value=3
)

petugas_lauk = st.sidebar.slider(
    "Petugas Isi Lauk",
    min_value=1,
    max_value=5,
    value=3
)

petugas_angkut = st.sidebar.slider(
    "Petugas Angkut",
    min_value=1,
    max_value=5,
    value=2
)

petugas_nasi = st.sidebar.slider(
    "Petugas Isi Nasi",
    min_value=1,
    max_value=5,
    value=2
)

# =====================
# PARAMETER WAKTU
# =====================
st.sidebar.markdown("### ⏱️ Parameter Waktu Proses (detik)")

lauk_min = st.sidebar.slider("Lauk Min", 10, 120, 30)
lauk_max = st.sidebar.slider("Lauk Max", 10, 120, 60)

angkut_min = st.sidebar.slider("Angkut Min", 10, 120, 20)
angkut_max = st.sidebar.slider("Angkut Max", 10, 120, 60)

nasi_min = st.sidebar.slider("Nasi Min", 10, 120, 30)
nasi_max = st.sidebar.slider("Nasi Max", 10, 120, 60)

# =====================
# TOMBOL AKSI
# =====================
st.sidebar.markdown("---")

run_button = st.sidebar.button("🚀 Jalankan Simulasi", use_container_width=True)
reset_button = st.sidebar.button("🔄 Reset Parameter", use_container_width=True)

if reset_button:
    st.session_state.clear()
    st.rerun()


if run_button:

    config = Config(
        NUM_MEJA=num_meja,
        MAHASISWA_PER_MEJA=mahasiswa_per_meja,
        PETUGAS_LAUK=petugas_lauk,
        PETUGAS_ANGKUT=petugas_angkut,
        PETUGAS_NASI=petugas_nasi,
        LAUK_MIN_TIME=lauk_min,
        LAUK_MAX_TIME=lauk_max,
        ANGKUT_MIN_TIME=angkut_min,
        ANGKUT_MAX_TIME=angkut_max,
        NASI_MIN_TIME=nasi_min,
        NASI_MAX_TIME=nasi_max
    )

    model = PiketOmprengDES(config)
    results, df = model.run()




    # tampilkan hasil di sini

# =========================================================
# METRICS
# =========================================================
# ============================
# PANEL INFORMASI AWAL
# ============================

if not run_button:
    st.title("🍱 Simulasi Sistem Piket Ompreng IT Del")

    st.markdown("## 🚀 Mulai Simulasi")

    st.info("""
    ### Langkah-langkah:
    1. Atur parameter simulasi di sidebar kiri
    2. Klik tombol **Jalankan Simulasi**
    3. Tunggu proses simulasi selesai
    4. Lihat hasil analisis dan visualisasi

    ### 📌 Parameter Default (Sesuai Soal)

    - Jumlah meja : **60**
    - Mahasiswa per meja : **3**
    - Total ompreng : **180**
    - Petugas lauk : **3 orang**
    - Petugas angkut : **2 orang**
    - Petugas nasi : **2 orang**
    - Waktu isi lauk : **30–60 detik**
    - Waktu angkut : **20–60 detik**
    - Waktu isi nasi : **30–60 detik**
    """)

    st.markdown("---")
    st.markdown("## 🎯 Preview Visualisasi")

    col1, col2 = st.columns(2)

    with col1:
        st.info("""
        📊 **Distribusi Waktu Penyelesaian**
        
        Histogram yang menunjukkan penyebaran waktu total
        dari ompreng dibuat sampai selesai.
        """)

    with col2:
        st.info("""
        📈 **Timeline Proses Ompreng**
        
        Menampilkan kapan ompreng mulai diproses
        dan kapan selesai.
        """)

    col3, col4 = st.columns(2)

    with col3:
        st.info("""
        🕒 **Distribusi Penyelesaian per Jam**
        
        Jumlah ompreng yang selesai setiap jam simulasi.
        """)

    with col4:
        st.info("""
        📦 **Durasi Tiap Tahap**
        
        Perbandingan waktu proses isi lauk dan isi nasi.
        """)

    st.stop()

    
st.title("🍱 Simulasi Sistem Piket Ompreng IT Del")

st.success(f"Simulasi selesai! {len(df)} ompreng diproses.")

durasi_total = df["total_waktu"].max() / 60
avg_time = df["total_waktu"].mean()

c1,c2,c3,c4 = st.columns(4)

c1.metric("Durasi Total", f"{durasi_total:.2f} menit")
c2.metric("Rata-rata Waktu Ompreng", f"{avg_time:.1f} detik")
c3.metric("Total Ompreng", len(df))
c4.metric("Total Petugas",
          petugas_lauk + petugas_angkut + petugas_nasi)

if run_button:
    results, df = model.run()
    st.session_state.df = df
    with st.expander("📄 Detail Hasil Simulasi", expanded=False):

        colA, colB = st.columns(2)

        # =========================
        # STATISTIK WAKTU TUNGGU
        # =========================
        with colA:

            st.subheader("Statistik Waktu Tunggu")

            avg_wait = df["total_waktu"].mean() / 60
            max_wait = df["total_waktu"].max() / 60
            min_wait = df["total_waktu"].min() / 60
            std_wait = df["total_waktu"].std() / 60

            st.write(f"Rata-rata: {avg_wait:.2f} menit")
            st.write(f"Maksimum: {max_wait:.2f} menit")
            st.write(f"Minimum: {min_wait:.2f} menit")
            st.write(f"Standar Deviasi: {std_wait:.2f} menit")

            st.markdown("---")

            st.subheader("Statistik Waktu Layanan")

            waktu_lauk = df["selesai_lauk"] - df["mulai_lauk"]
            waktu_nasi = df["selesai_nasi"] - df["mulai_nasi"]
            total_service = waktu_lauk + waktu_nasi

            st.write(f"Rata-rata: {(total_service.mean()/60):.2f} menit")
            st.write(f"Total: {(total_service.sum()/60):.2f} menit")

        # =========================
        # UTILISASI & PARAMETER
        # =========================
        with colB:

            st.subheader("Utilisasi per Kelompok")

            total_time = df["selesai_nasi"].max()

            util_lauk = (model.busy_lauk /
                        (total_time * config.PETUGAS_LAUK)) * 100

            util_nasi = (model.busy_nasi /
                        (total_time * config.PETUGAS_NASI)) * 100

            st.write(f"Petugas Lauk: {util_lauk:.1f}%")
            st.write(f"Petugas Nasi: {util_nasi:.1f}%")

            st.markdown("---")

            st.subheader("Parameter Simulasi")
            st.write(f"Jumlah Mahasiswa: {config.TOTAL_OMPRENG}")
            st.write(f"Jumlah Meja: {config.NUM_MEJA}")
            st.write(f"Mahasiswa per Meja: {config.MAHASISWA_PER_MEJA}")
            st.write(f"Petugas Lauk: {config.PETUGAS_LAUK}")
            st.write(f"Petugas Angkut: {config.PETUGAS_ANGKUT}")
            st.write(f"Petugas Nasi: {config.PETUGAS_NASI}")

            st.write(
                f"Waktu Mulai: {config.START_HOUR:02d}:{config.START_MINUTE:02d}"
            )

            st.write(
                f"Rentang Lauk: {config.LAUK_MIN_TIME}-{config.LAUK_MAX_TIME} detik"
            )
            st.write(
                f"Rentang Nasi: {config.NASI_MIN_TIME}-{config.NASI_MAX_TIME} detik"
            )
        


# =========================================================
# VISUALISASI
# =========================================================

st.header("📊 Visualisasi Hasil")

# =========================================================
# STYLE VISUAL
# =========================================================

PLOT_TEMPLATE = "plotly_dark"

COLOR_MAIN = "#4CC9F0"
COLOR_SECOND = "#F72585"
COLOR_THIRD = "#B8F2E6"
COLOR_AVG = "#FF595E"

st.markdown("""
<style>
.card {
    background-color: #1f3347;
    padding: 20px;
    border-radius: 12px;
    margin-bottom: 20px;
}

.card-title {
    font-size: 18px;
    font-weight: 600;
    color: #7ec8ff;
    margin-bottom: 8px;
}

.card-desc {
    font-size: 14px;
    color: #bcd6f0;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)


# =========================
# DISTRIBUSI WAKTU
# =========================
if run_button:

    # BUAT FIGURE DULU
    avg_wait = df["total_waktu"].mean()/60
    median_wait = df["total_waktu"].median()/60

    fig1 = px.histogram(
        df,
        x=df["total_waktu"]/60,
        nbins=35,
        template="plotly_dark",
        title="Distribusi Waktu Tunggu Mahasiswa",
        labels={"x":"Waktu Tunggu (menit)", "y":"Frekuensi"}
    )

    fig1.add_vline(
        x=avg_wait,
        line_dash="dash",
        line_color="red",
        annotation_text=f"Rata-rata: {avg_wait:.2f}"
    )


    col1, col2 = st.columns(2)

    with col1:

        st.markdown("""
    <div class="card">
        <div class="card-title">📊 Distribusi Waktu Penyelesaian</div>
        <div class="card-desc">
        Histogram yang menunjukkan penyebaran waktu total dari ompreng dibuat sampai selesai.
        </div>
    </div>
    """, unsafe_allow_html=True)

        if run_button:
            st.plotly_chart(
                fig1,
                use_container_width=True,
                key="histogram"
            )

    with col2:

        st.markdown("""
        <div class="card">
            <div class="card-title">📈 Timeline Proses Ompreng</div>
            <div class="card-desc">
            Menampilkan kapan ompreng mulai diproses dan kapan selesai.
            </div>
        </div>
        """, unsafe_allow_html=True)

        fig2 = px.scatter(
            df,
            x=df["mulai_lauk"]/60,
            y="id",
            template="plotly_dark",
            title="Timeline Kedatangan dan Penyelesaian",
            labels={"x":"Waktu Simulasi (menit)", "id":"ID Mahasiswa"}
        )

        fig2.update_traces(marker=dict(color="blue", size=5), name="Datang")

        fig2.add_scatter(
            x=df["selesai_nasi"]/60,
            y=df["id"],
            mode="markers",
            marker=dict(color="green", size=5),
            name="Selesai"
)

        fig2.update_layout(
            xaxis_title="Waktu Simulasi (detik)",
            yaxis_title="ID Mahasiswa"
    )
        if run_button:
            st.plotly_chart(
                fig2,
                use_container_width=True,
                key="timeline"
            )

    
    col3, col4 = st.columns(2)

    with col3:
        hourly = df["jam_selesai"].dt.hour.value_counts().sort_index()
        st.info("""
        🕒 **Distribusi Penyelesaian per Jam**
        
        Jumlah ompreng yang selesai setiap jam simulasi.
        """)

        queue_time = np.sort(df["mulai_lauk"].values)
        queue_len = np.arange(1, len(queue_time)+1)

        fig3 = px.line(
            x=queue_time/60,
            y=queue_len,
            template="plotly_dark",
            title="Panjang Antrian Sepanjang Waktu",
            labels={"x":"Waktu (menit)", "y":"Panjang Antrian"}
        )
    
        fig3 = px.bar(
            x=hourly.index,
            y=hourly.values,
            template="plotly_dark",
            title=""
        )

        fig3.update_traces(
            marker_color="#B8F2E6",
            marker_line_color="white",
            marker_line_width=1.5
        )

        fig3.update_layout(
            xaxis_title="Jam",
            yaxis_title="Jumlah Ompreng"
        )

        if run_button:
            st.plotly_chart(fig3,
                            use_container_width=True,
                            key="perjam")
        
    with col4:
        
        st.info("""
        📦 **Durasi Tiap Tahap**
        
        Perbandingan waktu proses isi lauk dan isi nasi.
        """)
       
        fig4 = px.box(
        df,
        y=["selesai_lauk", "selesai_nasi"],
        template="plotly_dark",
        title=""
        )

        fig4.update_layout(
            yaxis_title="Waktu (detik)"
    )
        if run_button:
            st.plotly_chart(fig4,
                            use_container_width=True,
                            key="durasi")
         
    service_time = (
    (df["selesai_lauk"] - df["mulai_lauk"]) +
    (df["selesai_nasi"] - df["mulai_nasi"])
    ) / 60

    

    avg_wait_minutes = df["total_waktu"].mean() / 60
    max_wait_minutes = df["total_waktu"].max() / 60

    fig5 = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=avg_wait_minutes,
        title={"text": "Rata-rata Waktu Tunggu Mahasiswa"},
        delta={"reference": 30},
        gauge={
            "axis": {"range": [0, max_wait_minutes]},
            "bar": {"color": "darkorange"},
            "steps": [
                {"range": [0, 20], "color": "#2ecc71"},
                {"range": [20, 40], "color": "#f1c40f"},
                {"range": [40, max_wait_minutes], "color": "#e74c3c"}
            ],
            "threshold": {
                "line": {"color": "red", "width": 3},
                "value": avg_wait_minutes
            }
        }
    ))

    completion_sorted = np.sort(df["selesai_nasi"].values)
    completed_count = np.arange(1, len(completion_sorted)+1)

    fig6 = px.line(
        x=completion_sorted/60,
        y=completed_count,
        template="plotly_dark",
        title="Throughput Sistem (Jumlah Ompreng Selesai)",
        labels={
            "x": "Waktu Simulasi (menit)",
            "y": "Jumlah Selesai"
        }
    )

    fig6.update_traces(
        line_color="#FFA15A",
        line_width=3
    )

col5, col6 = st.columns(2)

col5.plotly_chart(fig5, use_container_width=True, key="service_dist")
col6.plotly_chart(fig6, use_container_width=True, key="throughput")
            
# =========================
# FORMAT DATA UNTUK TABEL
# =========================

df_display = df.copy()

df_display["ID Mahasiswa"] = df_display["id"]
df_display["waktu_datang"] = df_display["mulai_lauk"]
df_display["waktu_mulai"] = df_display["mulai_lauk"]
df_display["waktu_selesai"] = df_display["selesai_nasi"]

df_display["Waktu Tunggu"] = (
    df_display["mulai_nasi"] - df_display["selesai_lauk"]
).clip(lower=0)

df_display["Waktu Layanan"] = (
    (df_display["selesai_lauk"] - df_display["mulai_lauk"]) +
    (df_display["selesai_nasi"] - df_display["mulai_nasi"])
)

df_display["Kelompok"] = (
    df_display["id"] % config.PETUGAS_NASI
)

df_display["Waktu Datang"] = df_display["mulai_lauk"].apply(
    lambda x: model.waktu_ke_jam(x)
)

df_display["Waktu Selesai"] = df_display["jam_selesai"]

df_display["jam"] = df_display["jam_selesai"].dt.hour

df_display = df_display[
    [
        "ID Mahasiswa",
        "waktu_datang",
        "waktu_mulai",
        "waktu_selesai",
        "Waktu Tunggu",
        "Waktu Layanan",
        "Kelompok",
        "Waktu Datang",
        "Waktu Selesai",
        "jam"
    ]
]

st.markdown("---")
st.header("📄 Data Hasil Simulasi")

with st.expander("Lihat Data", expanded=False):

    st.dataframe(
        df_display,
        use_container_width=True,
        height=450
    )

    csv = df_display.to_csv(index=False).encode("utf-8")

    st.download_button(
        "📥 Download Data CSV",
        csv,
        file_name="hasil_simulasi.csv",
        mime="text/csv",
        use_container_width=True
    )

st.markdown("---")

from datetime import datetime
now = datetime.now().strftime("%d/%m/%Y %H:%M")

st.markdown(
    f"""
    <div style="text-align:center; font-size:12px; color:gray;">
        © {datetime.now().year} Jose Napitupulu — MODSIM: Discrete Event System (DES)<br>
        Terakhir diperbarui: {now}
    </div>
    """,
    unsafe_allow_html=True
)