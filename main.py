import xbee
import time
import machine
import sht31_i2c_xbee

# TEMP_OFFSET = 14.0  # 内部温度上昇
# addr = xbee.ADDR_BROADCAST # ブロードキャスト用のアドレス
addr = xbee.ADDR_COORDINATOR  # cordinatorのアドレス

xb = xbee.XBee()

i2c = machine.I2C(1, freq=400000)
sht = sht31_i2c_xbee.SHT31(i2c)

while True:
    status = xbee.atcmd('AI')  # ネットワーク参加状態を確認する
    if status == 0x00:  # 参加状態の時にループを抜ける
        break
    print('.', end='')
    xbee.atcmd('CB', 0x01)  # コミッショニング(0x01:ネットワーク参加)
    time.sleep_ms(2000)  # 2秒間の待ち時間処理

print('\nJoined')

polling_ms = 5 * 1000  # ネットワーク離脱防止用のポーリング間隔
tr_interval_ms = 30 * 1000  # データ送信間隔
tr_time = time.ticks_ms() - tr_interval_ms

while True:
    # ネットワーク離脱防止用のpolling処理
    status = xbee.atcmd('AI')  # ネットワーク参加状態を確認する(polling代わりの暫定案)

    # XBeeスリープ
    sleep_time = polling_ms if polling_ms < tr_interval_ms else tr_interval_ms
    xb.sleep_now(sleep_time)

    # データ送信処理
    delta = time.ticks_diff(time.ticks_ms(), tr_time)  # 前回の送信時刻からの差分
    if delta < tr_interval_ms:
        continue

    temp, humid = sht.read_temp_and_humid()
    payload = str(temp) + ',' + str(humid)
    try:
        xbee.transmit(addr, payload)  # 取得値をXBeeで送信する
        print('send:', payload)
        tr_time = time.ticks_ms()
    except OSError as e:
        print("OSError : {}".format(e))
        time.sleep_ms(2000)  # 2秒間の待ち時間処理
        xbee.atcmd('FR')  # software rest (MycroPythonスクリプト再起動)
