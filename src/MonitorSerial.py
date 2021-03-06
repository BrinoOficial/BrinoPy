#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Br.ino Qt monitor serial

Codigo do monitor serial da IDE Br.ino
em PyQt5 (python 3.6)

    IDE do Br.ino  Copyright (C) 2018  Br.ino

    Este arquivo e parte da IDE do Br.ino.

    A IDE do Br.ino e um software livre: voce pode redistribui-lo
    e / ou modifica-lo de acordo com os termos da Licenca Publica
    Geral GNU, conforme publicado pela Free Software Foundation,
    seja a versao 3 da Licenca , ou (na sua opcao) qualquer
    versao posterior.

    A IDE do Br.ino e distribuida na esperanca de que seja util,
    mas SEM QUALQUER GARANTIA; sem a garantia implicita de
    COMERCIALIZACAO ou ADEQUACAO A UM DETERMINADO PROPOSITO.
    Consulte a Licenca Publica Geral GNU para obter mais detalhes.

    Voce deveria ter recebido uma copia da Licenca Publica Geral
    GNU junto com este programa. Caso contrario, veja
    <https://www.gnu.org/licenses/>

website: brino.cc
author: Mateus Berardo
email: mateus.berardo@brino.cc
contributor: Victor Rodrigues Pacheco
email: victor.pacheco@brino.cc
"""

import serial
import time
import threading

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import QWidget, QGridLayout, QPlainTextEdit, QLineEdit, QPushButton, QCheckBox, QComboBox

import Preferencias


class MonitorSerial(QWidget):
    _sinal_recebido_ = pyqtSignal(str)

    def __init__(self, parent=None):
        super(MonitorSerial, self).__init__(parent)
        # Define widgets
        self.linha_envio = QLineEdit(self)
        self.log_monitor = QPlainTextEdit(self)
        self.velocidade = QComboBox(self)
        self.velocidade.addItems(
            ("300", "600", "1200", "2400", "4800", "9600", "14400", "19200", "28800", "38400", "57600", "115200"))
        self.velocidade.setCurrentText("9600")
        self.velocidade.currentTextChanged.connect(self.mudar_velocidade)
        self.conexao = None
        self.parar = True
        self.last = ''
        self.thread_monitor = threading.Thread(target=self.serial_listener, args=(id, lambda: self.parar))
        self.init_ui()

    def keyPressEvent(self, e):
        """
        Fecha o monitor serial quando Esc eh precionado
        :param e:
            caractere pressionado
        :return:
            None
        """
        if e.key() == Qt.Key_Escape:
            self.close()

    def init_ui(self):
        """
        Inicializa a interface gráfica
        :return:
            None
        """
        # Define o layout do monitor serial
        self.setGeometry(650, 50, 400, 500)
        layout = QGridLayout(self)
        layout.setColumnStretch(0, 8)
        layout.setColumnStretch(1, 2)
        layout.setColumnStretch(2, 2)
        layout.setRowStretch(0, 1)
        layout.setRowStretch(1, 12)
        layout.setRowStretch(2, 1)
        self.setStyleSheet("background:#252525")
        self.setWindowTitle('Monitor Serial')

        self.linha_envio.setStyleSheet("border-radius:3px;background:#101010;margin-bottom:2px;margin-right:2px;")

        self.log_monitor.setReadOnly(True)
        self.log_monitor.setStyleSheet("border-radius:3px;background:#101010;margin-bottom:2px;margin-right:2px;")
        self._sinal_recebido_.connect(self.inserir_texto)

        btn_enviar = QPushButton("Enviar")
        btn_enviar.setObjectName("btn_enviar_tag")
        btn_enviar.setStyleSheet("""#btn_enviar_tag{border-radius:2px;color:#252525;background:#5cb50d;margin:2px;}
                                    #btn_enviar_tag:hover{border:1px solid #5cb50d;color:#5cb50d;background:#252525}""")
        btn_enviar.clicked.connect(self.enviar)

        btn_limpar = QPushButton("Limpar")
        btn_limpar.setObjectName("btn_limpar")
        btn_limpar.setStyleSheet("""#btn_limpar_tag{border-radius:2px;color:#252525;background:#5cb50d;margin:2px;}
                                    #btn_limpar_tag:hover{border:1px solid #5cb50d;color:#5cb50d;background:#252525}""")
        btn_limpar.clicked.connect(self.limpar)

        self.rolagem_check = QCheckBox(self)
        self.rolagem_check.setChecked(True)
        self.rolagem_check.setText("Rolagem-automática")

        layout.addWidget(self.linha_envio, 0, 0)
        layout.addWidget(self.log_monitor, 1, 0, 1, 0)
        layout.addWidget(btn_enviar, 0, 2)
        layout.addWidget(self.rolagem_check, 2, 0)
        layout.addWidget(self.velocidade, 2, 1)
        layout.addWidget(btn_limpar, 2, 2)

    def mudar_velocidade(self):
        self.desconectar()
        self.conectar(Preferencias.get("serial.port"), baud=int(self.velocidade.currentText()))

    def conectar(self, porta, baud=9600):
        """
        Conectar o monitor serial a porta serial
        :param porta:
            Porta serial que recebe os dados
        :param baud:
            Velocidade da porta
        :return:
        """
        try:
            self.conexao = serial.Serial(porta, baud)
            time.sleep(0.1)
            self.parar = False
            self.thread_monitor.start()
            return True
        except IOError:
            return False

    def inserir_texto(self, texto):
        """
        Insere o texto recebido pela porta serial no terminal
        :param texto:
            O texto que sera mostrado
        :return:
            None
        """
        self.log_monitor.insertPlainText(texto)

        if self.rolagem_check.isChecked():
            self.log_monitor.moveCursor(QTextCursor.End)

    def desconectar(self):
        """
        Desconecta a porta serial
        :return:
            None
        """
        if self.parar == False:
            self.parar = True
            self.thread_monitor.join()
            self.thread_monitor = threading.Thread(target=self.serial_listener, args=(id, lambda: self.parar))
            self.conexao.close()
            time.sleep(0.5)
            return True
        return False

    def enviar(self):
        """
        Enviar comandos pela serial pro Arduino
        :return:
            None
        """
        self.conexao.write(self.linha_envio.text().encode('utf-8'))
        self.linha_envio.setText("")

    def limpar(self):
        """
        Limpa o log do Monitor Serial
        :return:
            None
        """
        self.log_monitor.clear()

    def serial_listener(self, nome, parar):
        """
        Aguarda mensagens via porta serial
        :param nome:
            nome
        :param parar:
            funcao para sair do loop infinito
        :return:
        """
        try:
            while not parar():
                while self.conexao.inWaiting() and not parar():
                    if parar():
                        break
                    self._sinal_recebido_.emit(self.conexao.read().decode("utf-8"))
                if parar():
                    break
        except UnicodeDecodeError:
            pass

    def closeEvent(self, event):
        """
        Parar e fechar o monitor serial
        :param event:
            Evento de fechamento
        :return:
            None
        """
        if not self.parar:
            self.desconectar()
        event.accept()
