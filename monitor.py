from core.watchdog_manager import activar_watchdog_para_workspace
import time

if __name__ == "__main__":
    print("🚀 Monitor de documentos iniciado.")
    obs1 = activar_watchdog_para_workspace("base_conocimiento")
    obs2 = activar_watchdog_para_workspace("facturas")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Finalizando monitoreo...")
        for obs in [obs1, obs2]:
            if obs:
                obs.stop()
                obs.join()
