#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Voorbeeld van een facturatie-app met een grafische interface (Tkinter).

Functies:
 - Invoeren van factuurgegevens, verkoper-, koper- en factuurregels
 - Opslaan van facturen/offertes in een SQLite-database (met document_type)
 - Genereren van PDF’s (facturen en offertes) in aparte mappen
 - Toevoegen van klanten en materialen (stock) en deze selecteerbaar maken
 - Met één knop (in combinatie met een keuze tussen factuur/offerte) wordt
   het document opgeslagen in de database én als PDF weggeschreven

Let op: installeer ReportLab met: pip install reportlab
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox
import datetime
import sqlite3
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# --- ScrollableFrame: Voor een scrollbare hoofdinhoud ---
class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self, borderwidth=0, background="#f0f0f0")
        self.vscrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vscrollbar.set)
        self.vscrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollable_frame = ttk.Frame(self.canvas, padding=(10,10,10,10))
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        
        # Bind de muiswielscroling (optioneel)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_mousewheel(self, event):
        # Voor Windows
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

# --- Facturatie Logica ---
class FactuurItem:
    def __init__(self, omschrijving, hoeveelheid, eenheidsprijs, btw_percentage, korting=0):
        self.omschrijving = omschrijving
        self.hoeveelheid = hoeveelheid
        self.eenheidsprijs = eenheidsprijs
        self.btw_percentage = btw_percentage
        self.korting = korting

    def totaal_excl_btw(self):
        prijs = self.hoeveelheid * self.eenheidsprijs
        return prijs - self.korting

    def btw_bedrag(self):
        return self.totaal_excl_btw() * self.btw_percentage / 100

    def totaal_incl_btw(self):
        return self.totaal_excl_btw() + self.btw_bedrag()

class Factuur:
    def __init__(self, factuurnummer, factuurdatum, verkoper, verkoper_btw, koper, koper_btw, items=None):
        self.factuurnummer = factuurnummer
        self.factuurdatum = factuurdatum
        self.verkoper = verkoper
        self.verkoper_btw = verkoper_btw
        self.koper = koper
        self.koper_btw = koper_btw
        self.items = items if items is not None else []

    def add_item(self, item):
        self.items.append(item)

    def totaal_excl_btw(self):
        return sum(item.totaal_excl_btw() for item in self.items)

    def totaal_btw(self):
        return sum(item.btw_bedrag() for item in self.items)

    def totaal_incl_btw(self):
        return self.totaal_excl_btw() + self.totaal_btw()

    def get_factuur_text(self):
        lines = []
        lines.append("=====================================")
        lines.append("               FACTUUR")
        lines.append("=====================================")
        lines.append(f"Factuurnummer: {self.factuurnummer}")
        lines.append(f"Factuurdatum:  {self.factuurdatum.strftime('%d-%m-%Y')}")
        lines.append("-------------------------------------")
        lines.append("Verkoper:")
        lines.append(f"  Naam:    {self.verkoper.get('naam')}")
        lines.append(f"  Adres:   {self.verkoper.get('adres')}")
        lines.append(f"  BTW-nr:  {self.verkoper_btw}")
        lines.append("-------------------------------------")
        lines.append("Koper:")
        lines.append(f"  Naam:    {self.koper.get('naam')}")
        lines.append(f"  Adres:   {self.koper.get('adres')}")
        lines.append(f"  BTW-nr:  {self.koper_btw}")
        lines.append("-------------------------------------")
        lines.append("Artikelen:")
        header = "{:<5} {:<30} {:>8} {:>14} {:>10} {:>16} {:>10}".format(
            "Nr", "Omschrijving", "Hoev.", "Eenheidsprijs", "Korting", "Subtotaal excl.", "BTW"
        )
        lines.append(header)
        for index, item in enumerate(self.items, start=1):
            totaal_excl = item.totaal_excl_btw()
            btw = item.btw_bedrag()
            line = "{:<5} {:<30} {:>8} {:>14.2f} {:>10.2f} {:>16.2f} {:>10.2f}".format(
                index, item.omschrijving, item.hoeveelheid,
                item.eenheidsprijs, item.korting, totaal_excl, btw
            )
            lines.append(line)
        lines.append("-------------------------------------")
        lines.append(f"Totaal exclusief BTW: {self.totaal_excl_btw():>10.2f}")
        lines.append(f"Totaal BTW:           {self.totaal_btw():>10.2f}")
        lines.append(f"Totaal inclusief BTW: {self.totaal_incl_btw():>10.2f}")
        lines.append("=====================================")
        return "\n".join(lines)

    def get_offerte_text(self):
        lines = []
        lines.append("=====================================")
        lines.append("              OFFERTE")
        lines.append("=====================================")
        lines.append(f"Offertenummer: {self.factuurnummer}")
        lines.append(f"Offertedatum:  {self.factuurdatum.strftime('%d-%m-%Y')}")
        lines.append("-------------------------------------")
        lines.append("Verkoper:")
        lines.append(f"  Naam:    {self.verkoper.get('naam')}")
        lines.append(f"  Adres:   {self.verkoper.get('adres')}")
        lines.append(f"  BTW-nr:  {self.verkoper_btw}")
        lines.append("-------------------------------------")
        lines.append("Klant:")
        lines.append(f"  Naam:    {self.koper.get('naam')}")
        lines.append(f"  Adres:   {self.koper.get('adres')}")
        lines.append("-------------------------------------")
        lines.append("Artikelen:")
        header = "{:<5} {:<30} {:>8} {:>14} {:>10} {:>16} {:>10}".format(
            "Nr", "Omschrijving", "Hoev.", "Eenheidsprijs", "Korting", "Subtotaal excl.", "BTW"
        )
        lines.append(header)
        for index, item in enumerate(self.items, start=1):
            totaal_excl = item.totaal_excl_btw()
            btw = item.btw_bedrag()
            line = "{:<5} {:<30} {:>8} {:>14.2f} {:>10.2f} {:>16.2f} {:>10.2f}".format(
                index, item.omschrijving, item.hoeveelheid,
                item.eenheidsprijs, item.korting, totaal_excl, btw
            )
            lines.append(line)
        lines.append("-------------------------------------")
        lines.append(f"Totaal exclusief BTW: {self.totaal_excl_btw():>10.2f}")
        lines.append(f"Totaal BTW:           {self.totaal_btw():>10.2f}")
        lines.append(f"Totaal inclusief BTW: {self.totaal_incl_btw():>10.2f}")
        lines.append("=====================================")
        lines.append("Let op: Dit is een offerte en geen definitieve factuur.")
        return "\n".join(lines)

# --- Hoofdapplicatie met scrollbare inhoud en verbeterde layout ---
class InvoiceApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Facturatie App")
        self.geometry("950x950")
        # Gebruik een ttk-thema voor een moderner uiterlijk
        style = ttk.Style(self)
        style.theme_use("clam")
        # Maak een scrollbare container voor de gehele inhoud
        self.scroll_frame = ScrollableFrame(self)
        self.scroll_frame.pack(fill="both", expand=True)
        self.invoice_items = []
        self.create_widgets(self.scroll_frame.scrollable_frame)
        self.init_db()

    def create_widgets(self, parent):
        # Maak alle frames als kind van 'parent' (de scrollbare inhoud)
        
        # Factuurgegevens
        frame_factuur = ttk.LabelFrame(parent, text="Factuurgegevens", padding=10)
        frame_factuur.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        frame_factuur.columnconfigure(3, weight=1)
        
        ttk.Label(frame_factuur, text="Factuurnummer:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entry_factuurnummer = ttk.Entry(frame_factuur, width=20)
        self.entry_factuurnummer.grid(row=0, column=1, padx=5, pady=5)
        self.entry_factuurnummer.insert(0, "2025-0001")

        ttk.Label(frame_factuur, text="Factuurdatum (dd-mm-jjjj):").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.entry_factuurdatum = ttk.Entry(frame_factuur, width=20)
        self.entry_factuurdatum.grid(row=0, column=3, padx=5, pady=5, sticky="ew")
        self.entry_factuurdatum.insert(0, datetime.datetime.now().strftime("%d-%m-%Y"))

        # Verkopergegevens
        frame_verkoper = ttk.LabelFrame(parent, text="Verkopergegevens", padding=10)
        frame_verkoper.grid(row=1, column=0, padx=10, pady=10, sticky="ew")
        for i in range(6):
            frame_verkoper.columnconfigure(i, weight=1)
            
        ttk.Label(frame_verkoper, text="Naam:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entry_verkoper_naam = ttk.Entry(frame_verkoper, width=30)
        self.entry_verkoper_naam.grid(row=0, column=1, padx=5, pady=5)
        self.entry_verkoper_naam.insert(0, "Bedrijf X")
        ttk.Label(frame_verkoper, text="Adres:").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.entry_verkoper_adres = ttk.Entry(frame_verkoper, width=30)
        self.entry_verkoper_adres.grid(row=0, column=3, padx=5, pady=5)
        self.entry_verkoper_adres.insert(0, "Hoofdstraat 1, 1000 Brussel")
        ttk.Label(frame_verkoper, text="BTW-nr:").grid(row=0, column=4, sticky="e", padx=5, pady=5)
        self.entry_verkoper_btw = ttk.Entry(frame_verkoper, width=20)
        self.entry_verkoper_btw.grid(row=0, column=5, padx=5, pady=5)
        self.entry_verkoper_btw.insert(0, "BE0123456789")

        # Kopergegevens
        frame_koper = ttk.LabelFrame(parent, text="Kopergegevens", padding=10)
        frame_koper.grid(row=2, column=0, padx=10, pady=10, sticky="ew")
        for i in range(6):
            frame_koper.columnconfigure(i, weight=1)
            
        ttk.Label(frame_koper, text="Naam:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entry_koper_naam = ttk.Entry(frame_koper, width=30)
        self.entry_koper_naam.grid(row=0, column=1, padx=5, pady=5)
        self.entry_koper_naam.insert(0, "Klant Y")
        ttk.Label(frame_koper, text="Adres:").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.entry_koper_adres = ttk.Entry(frame_koper, width=30)
        self.entry_koper_adres.grid(row=0, column=3, padx=5, pady=5)
        self.entry_koper_adres.insert(0, "Marktplein 5, 2000 Antwerpen")
        ttk.Label(frame_koper, text="BTW-nr:").grid(row=0, column=4, sticky="e", padx=5, pady=5)
        self.entry_koper_btw = ttk.Entry(frame_koper, width=20)
        self.entry_koper_btw.grid(row=0, column=5, padx=5, pady=5)
        self.entry_koper_btw.insert(0, "BE9876543210")

        # Factuurregel toevoegen
        frame_item = ttk.LabelFrame(parent, text="Factuurregel toevoegen", padding=10)
        frame_item.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        for i in range(11):
            frame_item.columnconfigure(i, weight=1)
            
        ttk.Label(frame_item, text="Omschrijving:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entry_item_omschrijving = ttk.Entry(frame_item, width=30)
        self.entry_item_omschrijving.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(frame_item, text="Hoeveelheid:").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.entry_item_hoeveelheid = ttk.Entry(frame_item, width=10)
        self.entry_item_hoeveelheid.grid(row=0, column=3, padx=5, pady=5)
        ttk.Label(frame_item, text="Eenheidsprijs:").grid(row=0, column=4, sticky="e", padx=5, pady=5)
        self.entry_item_eenheidsprijs = ttk.Entry(frame_item, width=10)
        self.entry_item_eenheidsprijs.grid(row=0, column=5, padx=5, pady=5)
        ttk.Label(frame_item, text="BTW %:").grid(row=0, column=6, sticky="e", padx=5, pady=5)
        self.entry_item_btw = ttk.Entry(frame_item, width=5)
        self.entry_item_btw.grid(row=0, column=7, padx=5, pady=5)
        ttk.Label(frame_item, text="Korting:").grid(row=0, column=8, sticky="e", padx=5, pady=5)
        self.entry_item_korting = ttk.Entry(frame_item, width=10)
        self.entry_item_korting.grid(row=0, column=9, padx=5, pady=5)
        btn_toevoegen = ttk.Button(frame_item, text="Voeg factuurregel toe", command=self.add_item)
        btn_toevoegen.grid(row=0, column=10, padx=10, pady=5)

        # Overzicht van toegevoegde factuurregels
        frame_list = ttk.LabelFrame(parent, text="Toegevoegde factuurregels", padding=10)
        frame_list.grid(row=4, column=0, padx=10, pady=10, sticky="ew")
        self.listbox_items = tk.Listbox(frame_list, width=120, height=8)
        self.listbox_items.pack(padx=5, pady=5, fill="both", expand=True)

        # Documenttype-selectie
        frame_doc_type = ttk.Frame(parent, padding=10)
        frame_doc_type.grid(row=5, column=0, padx=10, pady=(10,0), sticky="w")
        self.doc_type = tk.StringVar(value="factuur")
        ttk.Label(frame_doc_type, text="Document Type:").grid(row=0, column=0, padx=5, pady=5)
        ttk.Radiobutton(frame_doc_type, text="Factuur", variable=self.doc_type, value="factuur").grid(row=0, column=1, padx=5, pady=5)
        ttk.Radiobutton(frame_doc_type, text="Offerte", variable=self.doc_type, value="offerte").grid(row=0, column=2, padx=5, pady=5)

        # Actieknop: Met 1 knop wordt het document opgeslagen en als PDF gegenereerd
        frame_actions = ttk.Frame(parent, padding=10)
        frame_actions.grid(row=6, column=0, padx=10, pady=10, sticky="ew")
        btn_generate_pdf = ttk.Button(frame_actions, text="Genereer PDF", command=self.generate_pdf_button)
        btn_generate_pdf.grid(row=0, column=0, padx=5)

        # Extra UI voor klanten
        frame_customers = ttk.LabelFrame(parent, text="Klant Toevoegen", padding=10)
        frame_customers.grid(row=7, column=0, padx=10, pady=10, sticky="ew")
        for i in range(4):
            frame_customers.columnconfigure(i, weight=1)
        ttk.Label(frame_customers, text="Naam:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entry_customer_naam = ttk.Entry(frame_customers, width=30)
        self.entry_customer_naam.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(frame_customers, text="Adres:").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.entry_customer_adres = ttk.Entry(frame_customers, width=30)
        self.entry_customer_adres.grid(row=0, column=3, padx=5, pady=5)
        ttk.Label(frame_customers, text="Telefoon:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.entry_customer_telefoon = ttk.Entry(frame_customers, width=20)
        self.entry_customer_telefoon.grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(frame_customers, text="E-mail:").grid(row=1, column=2, sticky="e", padx=5, pady=5)
        self.entry_customer_email = ttk.Entry(frame_customers, width=30)
        self.entry_customer_email.grid(row=1, column=3, padx=5, pady=5)
        btn_save_customer = ttk.Button(frame_customers, text="Opslaan Klant", command=self.save_customer_to_db_button)
        btn_save_customer.grid(row=2, column=0, columnspan=4, pady=5)

        # Extra UI voor materialen
        frame_materials = ttk.LabelFrame(parent, text="Materiaal Toevoegen", padding=10)
        frame_materials.grid(row=8, column=0, padx=10, pady=10, sticky="ew")
        for i in range(4):
            frame_materials.columnconfigure(i, weight=1)
        ttk.Label(frame_materials, text="Naam:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.entry_material_naam = ttk.Entry(frame_materials, width=30)
        self.entry_material_naam.grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(frame_materials, text="Beschrijving:").grid(row=0, column=2, sticky="e", padx=5, pady=5)
        self.entry_material_beschrijving = ttk.Entry(frame_materials, width=40)
        self.entry_material_beschrijving.grid(row=0, column=3, padx=5, pady=5)
        ttk.Label(frame_materials, text="Eenheidsprijs:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.entry_material_eenheidsprijs = ttk.Entry(frame_materials, width=15)
        self.entry_material_eenheidsprijs.grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(frame_materials, text="Voorraad:").grid(row=1, column=2, sticky="e", padx=5, pady=5)
        self.entry_material_voorraad = ttk.Entry(frame_materials, width=15)
        self.entry_material_voorraad.grid(row=1, column=3, padx=5, pady=5)
        btn_save_material = ttk.Button(frame_materials, text="Opslaan Materiaal", command=self.save_material_to_db_button)
        btn_save_material.grid(row=2, column=0, columnspan=4, pady=5)

        # Extra UI voor het selecteren van een bestaande klant
        frame_select_customer = ttk.LabelFrame(parent, text="Selecteer Klant", padding=10)
        frame_select_customer.grid(row=9, column=0, padx=10, pady=10, sticky="ew")
        btn_view_customers = ttk.Button(frame_select_customer, text="Bekijk Klanten", command=self.show_customers)
        btn_view_customers.grid(row=0, column=0, padx=5, pady=5)

        # Extra UI voor het selecteren van een bestaand materiaal
        frame_select_material = ttk.LabelFrame(parent, text="Selecteer Materiaal", padding=10)
        frame_select_material.grid(row=10, column=0, padx=10, pady=10, sticky="ew")
        btn_view_materials = ttk.Button(frame_select_material, text="Bekijk Materialen", command=self.show_materials)
        btn_view_materials.grid(row=0, column=0, padx=5, pady=5)

    def add_item(self):
        omschrijving = self.entry_item_omschrijving.get()
        try:
            hoeveelheid = float(self.entry_item_hoeveelheid.get())
            eenheidsprijs = float(self.entry_item_eenheidsprijs.get())
            btw_percentage = float(self.entry_item_btw.get())
            korting = float(self.entry_item_korting.get()) if self.entry_item_korting.get() else 0
        except ValueError:
            messagebox.showerror("Fout", "Voer geldige numerieke waarden in voor hoeveelheid, eenheidsprijs, BTW en korting.")
            return
        if not omschrijving:
            messagebox.showerror("Fout", "Omschrijving mag niet leeg zijn.")
            return
        item = FactuurItem(omschrijving, hoeveelheid, eenheidsprijs, btw_percentage, korting)
        self.invoice_items.append(item)
        self.listbox_items.insert(tk.END, f"{omschrijving} | Hoev.: {hoeveelheid} | Prijs: {eenheidsprijs} | BTW: {btw_percentage}% | Korting: {korting}")
        self.entry_item_omschrijving.delete(0, tk.END)
        self.entry_item_hoeveelheid.delete(0, tk.END)
        self.entry_item_eenheidsprijs.delete(0, tk.END)
        self.entry_item_btw.delete(0, tk.END)
        self.entry_item_korting.delete(0, tk.END)

    def build_invoice(self):
        factuurnummer = self.entry_factuurnummer.get()
        try:
            factuurdatum = datetime.datetime.strptime(self.entry_factuurdatum.get(), "%d-%m-%Y")
        except ValueError:
            messagebox.showerror("Fout", "Ongeldige datum. Gebruik het formaat dd-mm-jjjj.")
            return None
        verkoper = {"naam": self.entry_verkoper_naam.get(), "adres": self.entry_verkoper_adres.get()}
        verkoper_btw = self.entry_verkoper_btw.get()
        koper = {"naam": self.entry_koper_naam.get(), "adres": self.entry_koper_adres.get()}
        koper_btw = self.entry_koper_btw.get()
        if not self.invoice_items:
            messagebox.showerror("Fout", "Voeg minstens één factuurregel toe.")
            return None
        factuur = Factuur(factuurnummer, factuurdatum, verkoper, verkoper_btw, koper, koper_btw, self.invoice_items)
        return factuur

    def show_preview(self, text, title="Preview"):
        preview_window = tk.Toplevel(self)
        preview_window.title(title)
        text_widget = tk.Text(preview_window, wrap="none", width=100, height=30)
        text_widget.insert("1.0", text)
        text_widget.config(state="disabled")
        text_widget.pack(padx=10, pady=10)

    # --- Database Functionaliteit ---
    def init_db(self):
        conn = sqlite3.connect("invoices.db")
        cursor = conn.cursor()
        # Tabel voor facturen met extra kolom document_type
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facturen (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                factuurnummer TEXT,
                factuurdatum TEXT,
                verkoper_naam TEXT,
                verkoper_adres TEXT,
                verkoper_btw TEXT,
                koper_naam TEXT,
                koper_adres TEXT,
                koper_btw TEXT,
                totaal_excl REAL,
                totaal_btw REAL,
                totaal_incl REAL,
                document_type TEXT
            )
        """)
        # Tabel voor factuurregels
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS factuurregels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                factuur_id INTEGER,
                omschrijving TEXT,
                hoeveelheid REAL,
                eenheidsprijs REAL,
                btw_percentage REAL,
                korting REAL,
                totaal_excl REAL,
                btw_bedrag REAL,
                totaal_incl REAL,
                FOREIGN KEY(factuur_id) REFERENCES facturen(id)
            )
        """)
        # Tabel voor klanten
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS klanten (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                naam TEXT,
                adres TEXT,
                telefoon TEXT,
                email TEXT
            )
        """)
        # Tabel voor materialen
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS materialen (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                naam TEXT,
                beschrijving TEXT,
                eenheidsprijs REAL,
                voorraad INTEGER
            )
        """)
        conn.commit()
        conn.close()

    def save_invoice_to_db(self, invoice):
        conn = sqlite3.connect("invoices.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO facturen (
                factuurnummer, factuurdatum,
                verkoper_naam, verkoper_adres, verkoper_btw,
                koper_naam, koper_adres, koper_btw,
                totaal_excl, totaal_btw, totaal_incl, document_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice.factuurnummer,
            invoice.factuurdatum.strftime("%Y-%m-%d"),
            invoice.verkoper.get("naam"),
            invoice.verkoper.get("adres"),
            invoice.verkoper_btw,
            invoice.koper.get("naam"),
            invoice.koper.get("adres"),
            invoice.koper_btw,
            invoice.totaal_excl_btw(),
            invoice.totaal_btw(),
            invoice.totaal_incl_btw(),
            "factuur"
        ))
        invoice_id = cursor.lastrowid
        for item in invoice.items:
            cursor.execute("""
                INSERT INTO factuurregels (
                    factuur_id, omschrijving, hoeveelheid, eenheidsprijs, btw_percentage, korting,
                    totaal_excl, btw_bedrag, totaal_incl
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                invoice_id,
                item.omschrijving,
                item.hoeveelheid,
                item.eenheidsprijs,
                item.btw_percentage,
                item.korting,
                item.totaal_excl_btw(),
                item.btw_bedrag(),
                item.totaal_incl_btw()
            ))
        conn.commit()
        conn.close()

    def save_quote_to_db(self, invoice):
        conn = sqlite3.connect("invoices.db")
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO facturen (
                factuurnummer, factuurdatum,
                verkoper_naam, verkoper_adres, verkoper_btw,
                koper_naam, koper_adres, koper_btw,
                totaal_excl, totaal_btw, totaal_incl, document_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            invoice.factuurnummer,
            invoice.factuurdatum.strftime("%Y-%m-%d"),
            invoice.verkoper.get("naam"),
            invoice.verkoper.get("adres"),
            invoice.verkoper_btw,
            invoice.koper.get("naam"),
            invoice.koper.get("adres"),
            invoice.koper_btw,
            invoice.totaal_excl_btw(),
            invoice.totaal_btw(),
            invoice.totaal_incl_btw(),
            "offerte"
        ))
        quote_id = cursor.lastrowid
        for item in invoice.items:
            cursor.execute("""
                INSERT INTO factuurregels (
                    factuur_id, omschrijving, hoeveelheid, eenheidsprijs, btw_percentage, korting,
                    totaal_excl, btw_bedrag, totaal_incl
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                quote_id,
                item.omschrijving,
                item.hoeveelheid,
                item.eenheidsprijs,
                item.btw_percentage,
                item.korting,
                item.totaal_excl_btw(),
                item.btw_bedrag(),
                item.totaal_incl_btw()
            ))
        conn.commit()
        conn.close()

    def generate_pdf_invoice(self, invoice):
        # Zorg dat de map voor factuur-PDF's bestaat
        folder = os.path.join("pdf", "facturen")
        os.makedirs(folder, exist_ok=True)
        pdf_file = os.path.join(folder, f"factuur_{invoice.factuurnummer}.pdf")
        c = canvas.Canvas(pdf_file, pagesize=letter)
        text_object = c.beginText(40, letter[1] - 40)
        for line in invoice.get_factuur_text().split('\n'):
            text_object.textLine(line)
        c.drawText(text_object)
        c.showPage()
        c.save()
        return pdf_file

    def generate_pdf_quote(self, invoice):
        # Zorg dat de map voor offerte-PDF's bestaat
        folder = os.path.join("pdf", "offertes")
        os.makedirs(folder, exist_ok=True)
        pdf_file = os.path.join(folder, f"offerte_{invoice.factuurnummer}.pdf")
        c = canvas.Canvas(pdf_file, pagesize=letter)
        text_object = c.beginText(40, letter[1] - 40)
        for line in invoice.get_offerte_text().split('\n'):
            text_object.textLine(line)
        c.drawText(text_object)
        c.showPage()
        c.save()
        return pdf_file

    def generate_pdf_button(self):
        invoice = self.build_invoice()
        if invoice is None:
            return
        # Afhankelijk van de keuze (factuur of offerte) wordt het document opgeslagen en een PDF gegenereerd
        if self.doc_type.get() == "factuur":
            try:
                self.save_invoice_to_db(invoice)
            except Exception as e:
                messagebox.showerror("Fout", f"Er is een fout opgetreden bij het opslaan in de database: {e}")
                return
            try:
                pdf_file = self.generate_pdf_invoice(invoice)
                messagebox.showinfo("Succes", f"Factuur PDF gegenereerd en opgeslagen:\n{pdf_file}")
            except Exception as e:
                messagebox.showerror("Fout", f"Er is een fout opgetreden bij het genereren van de PDF: {e}")
        else:
            try:
                self.save_quote_to_db(invoice)
            except Exception as e:
                messagebox.showerror("Fout", f"Fout bij opslaan offerte in DB: {e}")
                return
            try:
                pdf_file = self.generate_pdf_quote(invoice)
                messagebox.showinfo("Succes", f"Offerte PDF gegenereerd en opgeslagen:\n{pdf_file}")
            except Exception as e:
                messagebox.showerror("Fout", f"Fout bij genereren offerte PDF: {e}")

    # --- Functies voor klanten ---
    def save_customer_to_db(self, naam, adres, telefoon, email):
        conn = sqlite3.connect("invoices.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO klanten (naam, adres, telefoon, email) VALUES (?, ?, ?, ?)", (naam, adres, telefoon, email))
        conn.commit()
        conn.close()

    def save_customer_to_db_button(self):
        naam = self.entry_customer_naam.get().strip()
        adres = self.entry_customer_adres.get().strip()
        telefoon = self.entry_customer_telefoon.get().strip()
        email = self.entry_customer_email.get().strip()
        if not naam:
            messagebox.showerror("Fout", "De klantnaam mag niet leeg zijn.")
            return
        try:
            self.save_customer_to_db(naam, adres, telefoon, email)
            messagebox.showinfo("Succes", "Klant succesvol opgeslagen in de database.")
            self.entry_customer_naam.delete(0, tk.END)
            self.entry_customer_adres.delete(0, tk.END)
            self.entry_customer_telefoon.delete(0, tk.END)
            self.entry_customer_email.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Fout", f"Er is een fout opgetreden bij het opslaan van de klant: {e}")

    # --- Functies voor materialen ---
    def save_material_to_db(self, naam, beschrijving, eenheidsprijs, voorraad):
        conn = sqlite3.connect("invoices.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO materialen (naam, beschrijving, eenheidsprijs, voorraad) VALUES (?, ?, ?, ?)",
                       (naam, beschrijving, eenheidsprijs, voorraad))
        conn.commit()
        conn.close()

    def save_material_to_db_button(self):
        naam = self.entry_material_naam.get().strip()
        beschrijving = self.entry_material_beschrijving.get().strip()
        try:
            eenheidsprijs = float(self.entry_material_eenheidsprijs.get())
            voorraad = int(self.entry_material_voorraad.get())
        except ValueError:
            messagebox.showerror("Fout", "Voer geldige numerieke waarden in voor eenheidsprijs en voorraad.")
            return
        if not naam:
            messagebox.showerror("Fout", "De materiaalnaam mag niet leeg zijn.")
            return
        try:
            self.save_material_to_db(naam, beschrijving, eenheidsprijs, voorraad)
            messagebox.showinfo("Succes", "Materiaal succesvol opgeslagen in de database.")
            self.entry_material_naam.delete(0, tk.END)
            self.entry_material_beschrijving.delete(0, tk.END)
            self.entry_material_eenheidsprijs.delete(0, tk.END)
            self.entry_material_voorraad.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror("Fout", f"Er is een fout opgetreden bij het opslaan van het materiaal: {e}")

    # --- Functie om alle klanten te tonen en een selectie te maken ---
    def show_customers(self):
        conn = sqlite3.connect("invoices.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, naam, adres, telefoon, email FROM klanten")
        customers = cursor.fetchall()
        conn.close()
        if not customers:
            messagebox.showinfo("Info", "Geen klanten gevonden.")
            return
        win = tk.Toplevel(self)
        win.title("Klant Selectie")
        lb = tk.Listbox(win, width=80)
        lb.pack(padx=10, pady=10)
        self.customer_data = customers
        for cust in customers:
            lb.insert(tk.END, f"ID: {cust[0]} - Naam: {cust[1]} - Adres: {cust[2]} - Telefoon: {cust[3]} - Email: {cust[4]}")
        def select_customer():
            selection = lb.curselection()
            if not selection:
                messagebox.showerror("Fout", "Selecteer een klant.")
                return
            index = selection[0]
            selected = self.customer_data[index]
            self.entry_koper_naam.delete(0, tk.END)
            self.entry_koper_naam.insert(0, selected[1])
            self.entry_koper_adres.delete(0, tk.END)
            self.entry_koper_adres.insert(0, selected[2])
            win.destroy()
        btn_select = ttk.Button(win, text="Selecteer Klant", command=select_customer)
        btn_select.pack(padx=10, pady=10)

    # --- Functie om alle materialen te tonen en een selectie te maken ---
    def show_materials(self):
        conn = sqlite3.connect("invoices.db")
        cursor = conn.cursor()
        cursor.execute("SELECT id, naam, beschrijving, eenheidsprijs, voorraad FROM materialen")
        materials = cursor.fetchall()
        conn.close()
        if not materials:
            messagebox.showinfo("Info", "Geen materialen gevonden.")
            return
        win = tk.Toplevel(self)
        win.title("Materiaal Selectie")
        lb = tk.Listbox(win, width=80)
        lb.pack(padx=10, pady=10)
        self.material_data = materials
        for mat in materials:
            lb.insert(tk.END, f"ID: {mat[0]} - Naam: {mat[1]} - Beschrijving: {mat[2]} - Prijs: {mat[3]} - Voorraad: {mat[4]}")
        def select_material():
            selection = lb.curselection()
            if not selection:
                messagebox.showerror("Fout", "Selecteer een materiaal.")
                return
            index = selection[0]
            selected = self.material_data[index]
            self.entry_item_omschrijving.delete(0, tk.END)
            self.entry_item_omschrijving.insert(0, f"{selected[1]} - {selected[2]}")
            self.entry_item_eenheidsprijs.delete(0, tk.END)
            self.entry_item_eenheidsprijs.insert(0, f"{selected[3]:.2f}")
            self.entry_item_hoeveelheid.delete(0, tk.END)
            self.entry_item_hoeveelheid.insert(0, "1")
            win.destroy()
        btn_select = ttk.Button(win, text="Selecteer Materiaal", command=select_material)
        btn_select.pack(padx=10, pady=10)

if __name__ == "__main__":
    app = InvoiceApp()
    app.mainloop()