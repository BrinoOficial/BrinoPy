#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Br.ino Qt UI

Interface base da IDE Br.ino
em PyQt5 (python 2.7)

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

import functools
import glob
import ntpath
import os
import sys
from tempfile import mkdtemp

import serial
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (QWidget, QGridLayout, QPlainTextEdit, QTabWidget, QActionGroup, QPushButton, QFileDialog,
                             QAction, QInputDialog, QMenu)

import DestaqueSintaxe
import EditorDeTexto
import Menu
import Preferencias
import Uploader
from BoasVindas import BoasVindas
from Compiler import compilar_arduino_builder
from GerenciadorDeKeywords import traduzir
from IndexadorContribuicao import IndexadorContribuicao
from Main import get_caminho_padrao
from PacoteAlvo import PacoteAlvo
from PlataformaAlvo import PlataformaAlvo


class Centro(QWidget):

    def __init__(self, parent=None):
        super(Centro, self).__init__()
        self.widget_abas = None
        self.menu = None
        self.parent = parent
        self.pacotes = dict()
        self.temp_build = mkdtemp('build')
        self.temp_cache = mkdtemp('cache')
        self.log = None
        self.init_ui()

    # noinspection PyUnresolvedReferences
    def init_ui(self):
        layout = QGridLayout(self)
        layout.setRowStretch(0, 7.5)
        layout.setRowStretch(1, 2.5)
        layout.setColumnMinimumWidth(0, 60)
        layout.setSpacing(5)
        layout.setContentsMargins(0, 0, 0, 0)

        self.menu = Menu.Menu(self)
        layout.addWidget(self.menu, 0, 0, 2, 2)

        # Botao para criar nova aba
        btn = QPushButton(self)
        btn.clicked.connect(self.nova_aba)
        btn.setStatusTip("Abrir nova aba")

        self.widget_abas = QTabWidget(self.parent)
        self.widget_abas.tabCloseRequested.connect(self.remover_aba)
        self.widget_abas.setTabsClosable(False)
        self.widget_abas.setCornerWidget(btn, Qt.TopRightCorner)
        self.widget_abas.setStyleSheet("background:#252525;")
        layout.addWidget(self.widget_abas, 0, 1, 1, 2)

        self.log = QPlainTextEdit(self)
        self.log.setStyleSheet("border-radius:5px;background:#101010;margin-bottom:5px;margin-right:5px;")
        self.log.setReadOnly(True)
        self.log.setStatusTip("Log")
        layout.addWidget(self.log, 1, 1, 1, 2)

        self.init_pacotes()
        self.criar_menu_placas()
        self.criar_menu_exemplos()

        self.widget_abas.addTab(BoasVindas(self), "Bem-Vindo")
        self.show()


    def init_pacotes(self):
        pasta_hardware = os.path.join('builder', 'hardware')
        self.indexer = IndexadorContribuicao(os.path.join('builder'), pasta_hardware)
        self.indexer.parse_index()
        self.indexer.sincronizar_com_arquivos()
        self.carregar_hardware_contribuido(self.indexer)
        self.carregar_hardware(pasta_hardware)
        # TODO carregar_hardware_rascunhos
        # TODO criar preferencias ferramentas

    def remover_aba(self, index):
        if self.widget_abas.count() > 1:
            if index is not int:
                self.widget_abas.removeTab(self.widget_abas.currentIndex())
            else:
                widget = self.widget_abas.widget(index)
                if widget is not None:
                    widget.deleteLater()
                self.widget_abas.removeTab(index)
        if self.widget_abas.count() == 1:
            self.widget_abas.setTabsClosable(False)

    def nova_aba(self, path="", salvar_caminho=True):
        if self.widget_abas.count() == 0 or path:
            editor = EditorDeTexto.CodeEditor(self.widget_abas, False, path=path, salvar_caminho=salvar_caminho)
        else:
            editor = EditorDeTexto.CodeEditor(self.widget_abas, True, path=path, salvar_caminho=salvar_caminho)
        if self.widget_abas.count() == 1:
            self.widget_abas.setTabsClosable(True)
        text = editor.get_nome()
        editor.setStyleSheet("background:#252525")
        highlight = DestaqueSintaxe.PythonHighlighter(editor.document())
        if editor.get_nome():
            self.widget_abas.addTab(editor, text)
        if editor.get_nome() == "":
            self.remover_aba(self.widget_abas.count() - 1)
        else:
            self.widget_abas.setCurrentIndex(self.widget_abas.count() - 1)
        editor.set_salvo(True)

    def abrir(self):
        dialogo = self.criar_dialogo_arquivo("Abrir arquivo", "Abrir")
        if dialogo.exec_() == QFileDialog.Accepted:
            caminho = dialogo.selectedFiles()[0]
            self.nova_aba(caminho)

    def salvar(self):
        editor = self.widget_abas.widget(self.widget_abas.currentIndex())
        caminho = editor.get_caminho()
        if caminho == 0:
            return
        editor.set_salvo(True)
        if caminho != "":
            if not os.path.exists(os.path.dirname(caminho)):
                try:
                    os.makedirs(os.path.dirname(caminho))
                except OSError as exc:  # Guard against race condition
                    if exc.errno != exc.errno.EEXIST:
                        raise
            with open(editor.get_caminho(), "w") as arquivo:
                arquivo.write(editor.get_texto())
        else:
            self.salvar_como()

    def salvar_como(self):
        dialogo = self.criar_dialogo_arquivo('Salvar arquivo', 'Salvar')
        if dialogo.exec_() == QFileDialog.Accepted:
            caminho = dialogo.selectedFiles()[0]
            if not ntpath.basename(caminho).__contains__(".brpp"):
                caminho = os.path.join(caminho, ntpath.basename(caminho) + ".brpp")
            editor = self.widget_abas.widget(self.widget_abas.currentIndex())
            self.widget_abas.setTabText(self.widget_abas.currentIndex(), ntpath.basename(caminho).replace(".brpp", ""))
            editor.set_caminho(caminho)
            self.salvar()

    def selecionar_texto(self, cursor, texto, indice_inicial, len):
        conteudo = self.widget_abas.widget(self.widget_abas.currentIndex()).toPlainText()
        indice_comeco = conteudo.find(texto, indice_inicial)
        cursor.setPosition(indice_comeco, QTextCursor.MoveAnchor)
        cursor.setPosition(indice_comeco + len, QTextCursor.KeepAnchor)
        return cursor

    def comentar_linha(self):
        editor = self.widget_abas.widget(self.widget_abas.currentIndex())
        cursor_atual = editor.textCursor()
        posicao = cursor_atual.position()
        linha = cursor_atual.blockNumber()
        bloco_atual = editor.document().findBlockByLineNumber(linha)
        cursor = QTextCursor(bloco_atual)
        editor.setTextCursor(cursor)
        texto = bloco_atual.text()
        if texto.strip().startswith("//"):
            cursor = self.selecionar_texto(cursor, '/', cursor.position(), 2)
            cursor.removeSelectedText()
            cursor.setPosition(posicao - 2)
            editor.setTextCursor(cursor)
        else:
            editor.insertPlainText('//')
            cursor.setPosition(posicao + 2)
            editor.setTextCursor(cursor)

    def achar(self):
        editor = self.widget_abas.widget(self.widget_abas.currentIndex())
        texto, ok = QInputDialog.getText(None, "Buscar", "Achar:")
        if ok and texto != "":
            cursor = editor.textCursor()
            cursor = self.selecionar_texto(cursor, texto, cursor.position(), len(texto))
            editor.setTextCursor(cursor)
        return

    def achar_e_substituir(self):
        editor = self.widget_abas.widget(self.widget_abas.currentIndex())
        subs = "haaaa"
        texto, ok = QInputDialog.getText(None, "Buscar", "Achar:")
        if ok and texto != "":
            cursor = editor.textCursor()
            cursor = self.selecionar_texto(cursor, texto, cursor.position(), len(texto))
            cursor.removeSelectedText()
            editor.setTextCursor(cursor)
            editor.insertPlainText(subs)
        return


    @staticmethod
    def criar_dialogo_arquivo(titulo, acao):
        dialogo = QFileDialog()
        dialogo.setWindowTitle(titulo)
        dialogo.setLabelText(QFileDialog.FileName, "Arquivo:")
        dialogo.setLabelText(QFileDialog.LookIn, "Buscar em:")
        dialogo.setLabelText(QFileDialog.FileType, "Tipo de arquivo:")
        dialogo.setLabelText(QFileDialog.Accept, acao)
        dialogo.setLabelText(QFileDialog.Reject, "Cancelar")
        dialogo.setNameFilters(["Rascunhos Br.ino (*.brpp)", "Rascunhos Arduino (*.ino)"])
        dialogo.selectNameFilter("Rascunhos Br.ino (*.brpp)")
        dialogo.setDirectory(get_caminho_padrao())
        return dialogo

    def abrir_serial(self):
        self.parent.abrir_serial()

    def carregar_hardware(self, pasta):
        if not os.path.isdir(pasta):
            return
        lista = [os.path.join(pasta, pasta_) for pasta_ in os.listdir(pasta) if
                 os.path.isdir(os.path.join(pasta, pasta_))]
        if len(lista) == 0:
            return
        lista = sorted(lista, key=str.lower)
        lista.remove(os.path.join(pasta, "tools"))
        for item in lista:
            nome_item = os.path.basename(item)
            if nome_item in self.pacotes:
                pacote_alvo = self.pacotes.get(nome_item)
            else:
                pacote_alvo = PacoteAlvo(nome_item)
                self.pacotes[nome_item] = pacote_alvo
            self.carregar_pacote_alvo(pacote_alvo, item)

    def carregar_hardware_contribuido(self, indexer):
        for pacote in indexer.criar_pacotes_alvo():
            if self.pacotes.get(pacote.get_id(), False):
                self.pacotes[pacote.get_id().encode('utf-8')] = pacote

    @staticmethod
    def carregar_pacote_alvo(pacote_alvo, pasta):
        pastas = os.listdir(pasta)
        if len(pastas) == 0:
            return
        for item in pastas:
            plataforma_alvo = PlataformaAlvo(item, os.path.join(pasta, item), pacote_alvo)
            pacote_alvo.get_plataformas()[item] = plataforma_alvo

    def criar_menu_placas(self):
        placas = QActionGroup(self.parent)
        placas.setExclusive(True)
        for pacote_alvo in self.pacotes.values():
            for plataforma_alvo in pacote_alvo.get_lista_plataformas():
                nome = plataforma_alvo.get_preferencias().get("name")
                self.parent.menu_placas.addAction(QAction(nome, self))
                for placa in plataforma_alvo.get_placas().values():
                    if not placa.get_preferencias().get('hide'):
                        self.parent.menu_placas.addAction(placa.criar_acao(self))

    def criar_menu_portas(self):
        for acao in self.parent.menu_portas.actions():
            self.parent.menu_portas.removeAction(acao)
        portas = QActionGroup(self.parent)
        portas.setExclusive(True)
        n_portas = len(self.serial_ports())
        if n_portas > 0:
            for porta in self.serial_ports():
                porta_acao = Porta.criar_acao(porta, self)
                self.parent.menu_portas.addAction(porta_acao)
                if n_portas == 1:
                    Preferencias.set('serial.port', porta)
        else:
            # TODO mensagem padrao sem portas
            pass

    def criar_menu_exemplos(self):
        caminho_exemplos = os.path.join('recursos', 'exemplos')
        for pasta_exemplo in [x for x in os.listdir(caminho_exemplos) if
                              os.path.isdir(os.path.join(caminho_exemplos, x))]:
            print pasta_exemplo
            menu = QMenu(pasta_exemplo)
            for exemplo in os.listdir(os.path.join(caminho_exemplos, pasta_exemplo)):
                exemplo_acao = QAction(exemplo, self)
                caminho_exemplo = os.path.join(caminho_exemplos, pasta_exemplo, exemplo)
                menu.addAction(exemplo_acao)
                exemplo_acao.triggered.connect(functools.partial(self.nova_aba, caminho_exemplo))
            self.parent.menu_exemplos.addMenu(menu)

    def on_troca_placa_ou_porta(self):
        plataforma = self.get_plataforma_alvo()
        pastas_bibliotecas = list()
        # if plataforma:
        #    core = self.get_preferencias_placa()
        pasta_plataforma = plataforma.get_pasta()
        pastas_bibliotecas.append(os.path.join(pasta_plataforma, 'libraries'))
        pastas_bibliotecas.append(os.path.join(get_caminho_padrao(), 'bibliotecas'))

    def get_preferencias_placa(self):
        placa_alvo = self.get_placa_alvo()
        if placa_alvo is None:
            return None
        id_placa = placa_alvo.get_id()
        prefs = placa_alvo.get_preferencias()
        nome_extendido = prefs.get("name")
        for id_menu in placa_alvo.get_ids_menus():
            if not placa_alvo.tem_menu(id_menu):
                continue
            entrada = Preferencias.get("custom_" + id_menu)
            if entrada is not None and entrada.startswith(id_placa):
                id_selecao = entrada[len(id_placa) + 1:]
                prefs.update(placa_alvo.get_preferencias_menu(id_menu, id_selecao))
                nome_extendido += ", " + placa_alvo.get_label_menu(id_menu, id_selecao)
        prefs['name'] = nome_extendido
        ferramentas = list()
        plataforma = self.indexer.get_plataforma_contribuida(self.get_plataforma_alvo())
        if plataforma is not None:
            ferramentas.extend(plataforma.get_ferramentas_resolvidas())

        core = prefs.get("build.core")
        if core is not None and core.__contains__(":"):
            separado = core.split(":")
            referenciada = self.get_plataforma_atual_do_pacote(separado[0])
            if referenciada is not None:
                plat_referenciada = self.indexer.get_plataforma_contribuida(referenciada)
                ferramentas.extend(plat_referenciada.get_ferramentas_resolvidas())
        prefix = "runtime.tools."
        for tool in ferramentas:
            pasta = tool.get_pasta_instalada()
            caminho = os.path.abspath(pasta)
            prefs[(prefix + tool.get_nome() + ".path").encode('utf-8')] = caminho
            Preferencias.set(prefix + tool.get_nome() + ".path", caminho)
            Preferencias.set(prefix + tool.get_nome() + "-" + tool.get_versao() + ".path", caminho)
        return prefs

    def get_placa_alvo(self):
        plataforma_alvo = self.get_plataforma_alvo()
        if plataforma_alvo:
            placa = Preferencias.get('board')
            return plataforma_alvo.get_placa(placa)

    def get_plataforma_alvo(self, pacote=None, plataforma=None):
        if pacote is None:
            pacote = Preferencias.get('target_package')
        if plataforma is None:
            plataforma = Preferencias.get('target_platform')
        p = self.pacotes.get(pacote)
        plataforma_alvo = p.get(plataforma)
        return plataforma_alvo

    def get_plataforma_atual_do_pacote(self, pacote):
        return self.get_plataforma_alvo(pacote, Preferencias.get("target_platform"))

    def compilar(self):
        self.salvar()
        self.log.clear()
        placa_alvo = self.get_placa_alvo()
        plataforma_alvo = placa_alvo.get_plataforma()
        pacote_alvo = plataforma_alvo.get_pacote()
        editor = self.widget_abas.widget(self.widget_abas.currentIndex())
        caminho = editor.get_caminho()
        if caminho == 0:
            return
        traduzir(caminho)
        resultado = compilar_arduino_builder(caminho, placa_alvo, plataforma_alvo, pacote_alvo, self.temp_build,
                                             self.temp_cache)
        self.log.insertPlainText(resultado)

    def upload(self):
        self.compilar()
        editor = self.widget_abas.widget(self.widget_abas.currentIndex())
        caminho = editor.get_caminho()
        if caminho == 0:
            return
        caminho_temp = self.temp_build
        uploader = None
        if uploader is None:
            uploader = Uploader.get_uploader_por_preferencias()
            uploader = Uploader.UploaderSerial(False)
        sucesso = False
        nome = os.path.basename(caminho).replace("brpp", "ino")
        sucesso = uploader.upload_usando_preferencias(self, caminho_temp, os.path.basename(nome))

    @staticmethod
    def serial_ports():
        """ Lists serial port names

            :raises EnvironmentError:
                On unsupported or unknown platforms
            :returns:
                A list of the serial ports available on the system
        """
        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            # this excludes your current terminal "/dev/tty"
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Unsupported platform')

        result = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass
        return result


class Porta:

    @staticmethod
    def criar_acao(porta, parent):
        acao_porta = QAction(porta, parent)
        acao_porta.triggered.connect(functools.partial(Porta.selecionar_porta, porta))
        return acao_porta

    @staticmethod
    def selecionar_porta(porta):
        Preferencias.set('serial.port', porta)
