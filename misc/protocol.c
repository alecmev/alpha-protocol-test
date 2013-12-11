// packet format
//
//   1     2          2         N    2    1
// <SOP><size><slave_address><data><crc><EOP>
// escaping SOP and EOP
// 0xFF -> 0xFF, 0xFF
// SOP  -> 0xFF, ( 0xFF ^ SOP )
// EOP  -> 0xFF, ( 0xFF ^ EOP )
// crc calculated  - size, slave_address,data
// size = slave_address,data,crc + 2(size)
#define SOP 0xE1
#define EOP 0xE2
#define ACK 0x00
#define NAK 0x01

// data format answer from slave
// 1 ACK or NAK
// 2 Status keyboard

// data format from master
// 1 Command    =   0 - SetMode, no data, store in EEPROM
//              =   1 - GetInput(status keyboard), no data
//              =   2 - SetID, data 2 byte ID, store in EEPROM
//              =   3 - SetSpeed(com port), data one byte =  0 - 9600, 1 -19200, 2 - 38400, 3 - 57600, 4 - 115200, store in EEPROM
//              =   4 - SetKeyConfig, data one byte = KeyConfig(default), KeyConfig store in EEPROM
//                      KeyConfig -> 
//                                  0-bit Bip_Dis, disable internal bipper
//                                  1-bit Key_Dis, disable internal keyboard
//                                  2-bit Rele,    on - off Rele for communicate automat internal 
//                                  3-bit Key_Act, immitation key activation ??
//                                  4-7-bit rezerved
//              =   5 - KeySeq,  data = KeyConfig(1 byte) , Ton(1 byte), Toff(1 byte), N(1 byte), K1...KN 
//                      KeyConfig - same as see up, init but NOT store in EEPROM
//                      Ton 1-255, time push keyboard in *5mS
//                      Toff 1-255, time releas keyboard(pause) in *5mS
//                      LengthSeq 1 - 64, length sequence
//                      K1, K2,..., KN - keyboard state in secunce, one bit one KEY 0-bit -> KEY1, 7-bit -> KEY8, "1" => Key ON, "0" -> Key OFF 
// 2 data if need, see up

uint16_t CRC16;

enum RECEIVE_STATE {
    WAIT_SOP,
    RECEIVE_DATA,
    PARSE_MESSAGE
};

enum COMMAND_LIST {
    SET_MODE,
    GET_INPUT,
    SET_ID,
    SET_SPEED,
    SET_KEY_CONFIG,
    KEY_SEQ
};

enum COM_SPEED_SELECT {
    SPEED_9600,
    SPEED_19200,
    SPEED_38400,
    SPEED_57600,
    SPEED_115200
};

//******************* slave send to master ***************************

SendMessage(uint8_t ack)
{
    uint16_t crcval = 0;
    uint16_t c, q;
    TxDataLength = 8;
    TxBuffer[0] = ByteOf(TxDataLength, 0);
    TxBuffer[1] = ByteOf(TxDataLength, 1);
    TxBuffer[2] = ByteOf(MyID, 0);
    TxBuffer[3] = ByteOf(MyID, 1);
    TxBuffer[4] = ack;
    TxBuffer[5] = Status;
    for (uint8_t i = 0; i < 6; i++) {
        c = TxBuffer[i];
        q = (crcval ^ c) & 017;
        crcval = (crcval >> 4) ^ (q * 010201);
        q = (crcval ^ (c >> 4)) & 017;
        crcval = (crcval >> 4) ^ (q * 010201);
    }

    CRC16 = crcval;
    TxBuffer[6] = ByteOf(CRC16, 0);
    TxBuffer[7] = ByteOf(CRC16, 1);
    putchar1(SOP);
    for (int c = 0; c < TxDataLength; c++) {
        if (TxBuffer[c] == 0xFF) {
            putchar1(0xFF);
            putchar1(0xFF);
        } else if ((TxBuffer[c] == SOP) || (TxBuffer[c] == EOP)) {
            putchar1(0xFF);
            putchar1(0xFF ^ TxBuffer[c]);
        } else {
            putchar1(TxBuffer[c]);
        }
    }

    putchar1(EOP);
}

if (hasinput1()) {
    uint8_t in = getchar1();
    switch (RxState) {
        case WAIT_SOP:
            if (in == SOP) {
                RxState = RECEIVE_DATA;
                RxDataLength = 0;
            }

            TimeoutRS = Time;
            break;

        case RECEIVE_DATA:
            if (in == EOP) {
                if (RxDataLength > 6) {   // adr + ID + CRC + data
                    uint16_t crcval = 0;
                    uint16_t c, q;
                    for (uint8_t i = 0; i < (RxDataLength); i++) {
                        c = RxBuffer[i];
                        q = (crcval ^ c) & 017;
                        crcval = (crcval >> 4) ^ (q * 010201);
                        q = (crcval ^ (c >> 4)) & 017;
                        crcval = (crcval >> 4) ^ (q * 010201);
                    }

                    CRC16 = crcval;
                    if (!CRC16) {
                        ParseMessage(); // Paket OK, go to parse message                                
                        RxState = WAIT_SOP; // wait new paket      
                    } else {
                        RxState = WAIT_SOP; // CRC error, go to wait new paket
                    }
                } else {
                    RxState = WAIT_SOP;
                }           // Format paket  error, go to wait new paket
            } else {
                if (process_escape) {
                    process_escape = false;
                    if (in == 0xff) {
                        RxBuffer[RxDataLength] = in;
                    } else {
                        RxBuffer[RxDataLength] = 0xff ^ in;
                    }
                    
                    RxDataLength++;
                } else {
                    if (in == 0xff) {
                        process_escape = true;
                    } else {
                        RxBuffer[RxDataLength] = in;
                        RxDataLength++;
                    }
                }

                if (RxDataLength >= RECEIVE_BUFFER_SIZE) {
                    RxState = WAIT_SOP;
                }
            }
            break;

        default:
            RxState = WAIT_SOP;
            break;
    }
}