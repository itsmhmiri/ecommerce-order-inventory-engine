"""
Invoice generation service using ReportLab.
Produces synchronous, in-process PDF invoices with itemized line snapshots, taxes, and payment status.
"""

import io
from decimal import Decimal
from typing import TYPE_CHECKING

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

if TYPE_CHECKING:
    from apps.orders.models import Order


class InvoiceService:
    """
    Synchronous PDF Invoice Generator.
    Compiles an immutable, itemized invoice PDF from Order data and snaps.
    """

    @classmethod
    def generate_pdf(cls, order: "Order") -> io.BytesIO:
        """
        Generates a clean, professional PDF invoice for the given Order.

        Args:
            order: Order instance with pre-fetched order items and payment transaction.

        Returns:
            io.BytesIO: In-memory byte buffer containing the generated PDF stream.
        """
        buffer = io.BytesIO()

        # Document setup: Letter size with 0.5 in (36 pt) margins
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=36,
        )

        styles = getSampleStyleSheet()

        # Custom typography styles
        title_style = ParagraphStyle(
            name="InvoiceTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#0F172A"),
        )
        company_style = ParagraphStyle(
            name="CompanyHeader",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#64748B"),
        )
        meta_label_style = ParagraphStyle(
            name="MetaLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#475569"),
        )
        meta_value_style = ParagraphStyle(
            name="MetaValue",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#0F172A"),
        )
        table_header_style = ParagraphStyle(
            name="TableHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#1E293B"),
        )
        table_cell_style = ParagraphStyle(
            name="TableCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#334155"),
        )
        table_cell_bold = ParagraphStyle(
            name="TableCellBold",
            parent=table_cell_style,
            fontName="Helvetica-Bold",
        )
        footer_style = ParagraphStyle(
            name="FooterText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#94A3B8"),
            alignment=1,  # Centered
        )

        story = []

        # 1. Header Banner: Brand Title & Invoice Header
        invoice_short_id = str(order.id).replace("-", "")[:8].upper()
        formatted_date = order.created_at.strftime("%B %d, %Y - %H:%M:%S UTC")

        header_data = [
            [
                Paragraph("<b>ORDER & INVENTORY ENGINE</b>", title_style),
                Paragraph(
                    f"<b>INVOICE</b><br/>#{invoice_short_id}",
                    ParagraphStyle(
                        name="InvNum",
                        fontName="Helvetica-Bold",
                        fontSize=14,
                        leading=18,
                        alignment=2,  # Right align
                        textColor=colors.HexColor("#2563EB"),
                    ),
                ),
            ],
            [
                Paragraph("High-Concurrency E-Commerce Core & Fulfillment", company_style),
                Paragraph(
                    f"Issued: {formatted_date}",
                    ParagraphStyle(
                        name="InvDate",
                        fontName="Helvetica",
                        fontSize=8.5,
                        leading=11,
                        alignment=2,
                        textColor=colors.HexColor("#64748B"),
                    ),
                ),
            ],
        ]
        header_table = Table(header_data, colWidths=[330, 210])
        header_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story.append(header_table)
        story.append(Spacer(1, 14))

        story.append(
            HRFlowable(
                width="100%",
                thickness=1.5,
                color=colors.HexColor("#E2E8F0"),
                spaceBefore=0,
                spaceAfter=14,
            )
        )

        # 2. Customer, Order Status & Payment Meta Table
        status_color = colors.HexColor("#D97706")  # Amber default for PENDING
        if order.status == "PAID":
            status_color = colors.HexColor("#16A34A")  # Green
        elif order.status in ("FAILED", "CANCELLED"):
            status_color = colors.HexColor("#DC2626")  # Red

        payment_status_text = "NOT PAID"
        gateway_ref_text = "N/A"
        payment_tx = getattr(order, "payment_transaction", None)
        if payment_tx is not None:
            payment_status_text = payment_tx.status
            gateway_ref_text = payment_tx.simulated_gateway_ref

        shipping_addr = (
            order.shipping_address if order.shipping_address.strip() else "Standard Digital Delivery / Not specified"
        )

        meta_info_data = [
            [
                Paragraph("<b>BILL TO:</b>", meta_label_style),
                Paragraph(f"{order.user.username} ({order.user.email or 'No email on file'})", meta_value_style),
                Paragraph("<b>ORDER ID:</b>", meta_label_style),
                Paragraph(str(order.id), meta_value_style),
            ],
            [
                Paragraph("<b>DELIVERY ADDRESS:</b>", meta_label_style),
                Paragraph(shipping_addr, meta_value_style),
                Paragraph("<b>ORDER STATUS:</b>", meta_label_style),
                Paragraph(f"<font color='{status_color.hexval()}'><b>{order.status}</b></font>", meta_value_style),
            ],
            [
                Paragraph("<b>PAYMENT STATUS:</b>", meta_label_style),
                Paragraph(f"<b>{payment_status_text}</b>", meta_value_style),
                Paragraph("<b>GATEWAY REF:</b>", meta_label_style),
                Paragraph(gateway_ref_text, meta_value_style),
            ],
        ]
        meta_table = Table(meta_info_data, colWidths=[120, 160, 100, 160])
        meta_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#F1F5F9")),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        story.append(meta_table)
        story.append(Spacer(1, 16))

        # 3. Itemized Order Line Items Table
        items_header = [
            Paragraph("<b>#</b>", table_header_style),
            Paragraph("<b>SKU</b>", table_header_style),
            Paragraph("<b>PRODUCT DESCRIPTION</b>", table_header_style),
            Paragraph("<b>UNIT PRICE</b>", ParagraphStyle(name="THRight", parent=table_header_style, alignment=2)),
            Paragraph("<b>QTY</b>", ParagraphStyle(name="THCenter", parent=table_header_style, alignment=1)),
            Paragraph("<b>SUBTOTAL</b>", ParagraphStyle(name="THRight2", parent=table_header_style, alignment=2)),
        ]

        items_rows = [items_header]
        items = list(order.items.all())
        subtotal_calc = Decimal("0.00")

        for idx, item in enumerate(items, start=1):
            subtotal_calc += item.subtotal
            items_rows.append(
                [
                    Paragraph(str(idx), table_cell_style),
                    Paragraph(item.sku, table_cell_bold),
                    Paragraph(item.product_title, table_cell_style),
                    Paragraph(
                        f"${item.unit_price:.2f}", ParagraphStyle(name="TCRight", parent=table_cell_style, alignment=2)
                    ),
                    Paragraph(
                        str(item.quantity), ParagraphStyle(name="TCCenter", parent=table_cell_style, alignment=1)
                    ),
                    Paragraph(
                        f"${item.subtotal:.2f}", ParagraphStyle(name="TCRight2", parent=table_cell_bold, alignment=2)
                    ),
                ]
            )

        items_table = Table(
            items_rows,
            colWidths=[24, 95, 215, 65, 45, 96],
        )
        items_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                    ("TOPPADDING", (0, 0), (-1, 0), 6),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("TOPPADDING", (0, 1), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )
        story.append(items_table)
        story.append(Spacer(1, 10))

        # 4. Financial Breakdown & Taxes Table
        # Compute taxes line item: 0.00 (Standard inclusive/exempt) to accurately reflect order financial schema
        taxes_amount = Decimal("0.00")
        total_amount = order.total_amount

        summary_data = [
            [
                Paragraph("<b>Items Subtotal:</b>", table_cell_style),
                Paragraph(f"${subtotal_calc:.2f}", ParagraphStyle(name="SR1", parent=table_cell_style, alignment=2)),
            ],
            [
                Paragraph("<b>Estimated Tax / VAT (0%):</b>", table_cell_style),
                Paragraph(f"${taxes_amount:.2f}", ParagraphStyle(name="SR2", parent=table_cell_style, alignment=2)),
            ],
            [
                Paragraph(
                    "<b>Grand Total:</b>",
                    ParagraphStyle(name="GrandTotalLbl", parent=table_cell_bold, fontSize=11, leading=14),
                ),
                Paragraph(
                    f"<b>${total_amount:.2f}</b>",
                    ParagraphStyle(
                        name="GrandTotalVal",
                        parent=table_cell_bold,
                        fontSize=11,
                        leading=14,
                        alignment=2,
                        textColor=colors.HexColor("#2563EB"),
                    ),
                ),
            ],
        ]

        summary_table = Table(summary_data, colWidths=[130, 96])
        summary_table.setStyle(
            TableStyle(
                [
                    ("LINEABOVE", (0, 0), (-1, 0), 0.5, colors.HexColor("#CBD5E1")),
                    ("LINEBELOW", (0, -1), (-1, -1), 1.5, colors.HexColor("#0F172A")),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                ]
            )
        )

        # Align summary to the right of page
        full_summary_table = Table([["", summary_table]], colWidths=[314, 226])
        full_summary_table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        story.append(full_summary_table)

        story.append(Spacer(1, 24))

        # 5. Footer & Audit Sign-Off
        story.append(
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#E2E8F0"),
                spaceBefore=0,
                spaceAfter=10,
            )
        )

        story.append(
            Paragraph(
                "Thank you for your business! This document is an officially generated electronic invoice. "
                "All inventory items, prices, and SKUs are recorded with immutable database audit guarantees.",
                footer_style,
            )
        )
        story.append(Spacer(1, 4))
        story.append(
            Paragraph(
                f"Order Reference: {order.id} | Generated In-Process via ReportLab Engine",
                footer_style,
            )
        )

        # Build PDF into in-memory buffer
        doc.build(story)
        buffer.seek(0)
        return buffer
