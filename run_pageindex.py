"""CLI entry point for PageIndex tree indexing and document processing.

Usage examples:
    # Tree indexing (original PageIndex functionality)
    python run_pageindex.py --pdf_path document.pdf
    python run_pageindex.py --md_path document.md

    # For search/ingestion, use the Python API:
    #   from pageindex import PageIndex
    #   pi = PageIndex(supabase_url='...', supabase_key='...')
    #   results = pi.search("query")
"""
import argparse
import asyncio
import json
import os

# Tree indexing functions (internal, not part of public search API)
from pageindex.page_index import page_index_main
from pageindex.page_index_md import md_to_tree
from pageindex.utils import ConfigLoader, config

if __name__ == "__main__":
    # For search and ingestion, use the PageIndex class:
    #   from pageindex import PageIndex
    #   pi = PageIndex(supabase_url='...', supabase_key='...')
    #   results = pi.search("sentenze Corte di Cassazione 2020")
    #   doc = pi.ingest(path='document.pdf')
    #
    # This CLI handles tree indexing (the original PageIndex functionality).

    # Set up argument parser
    parser = argparse.ArgumentParser(description='Process PDF or Markdown document and generate structure')
    parser.add_argument('--pdf_path', type=str, help='Path to the PDF file')
    parser.add_argument('--md_path', type=str, help='Path to the Markdown file')

    parser.add_argument('--model', type=str, default=None, help='Model to use')

    parser.add_argument('--toc-check-pages', type=int, default=20,
                      help='Number of pages to check for table of contents (PDF only)')
    parser.add_argument('--max-pages-per-node', type=int, default=10,
                      help='Maximum number of pages per node (PDF only)')
    parser.add_argument('--max-tokens-per-node', type=int, default=20000,
                      help='Maximum number of tokens per node (PDF only)')

    parser.add_argument('--if-add-node-id', type=str, default='yes',
                      help='Whether to add node id to the node')
    parser.add_argument('--if-add-node-summary', type=str, default='yes',
                      help='Whether to add summary to the node')
    parser.add_argument('--if-add-doc-description', type=str, default='no',
                      help='Whether to add doc description to the doc')
    parser.add_argument('--if-add-node-text', type=str, default='no',
                      help='Whether to add text to the node')

    # Markdown specific arguments
    parser.add_argument('--if-thinning', type=str, default='no',
                      help='Whether to apply tree thinning for markdown (markdown only)')
    parser.add_argument('--thinning-threshold', type=int, default=5000,
                      help='Minimum token threshold for thinning (markdown only)')
    parser.add_argument('--summary-token-threshold', type=int, default=200,
                      help='Token threshold for generating summaries (markdown only)')
    args = parser.parse_args()

    # Validate that exactly one file type is specified
    if not args.pdf_path and not args.md_path:
        raise ValueError("Either --pdf_path or --md_path must be specified")
    if args.pdf_path and args.md_path:
        raise ValueError("Only one of --pdf_path or --md_path can be specified")

    if args.pdf_path:
        # Validate PDF file
        if not args.pdf_path.lower().endswith('.pdf'):
            raise ValueError("PDF file must have .pdf extension")
        if not os.path.isfile(args.pdf_path):
            raise ValueError(f"PDF file not found: {args.pdf_path}")

        # Build provider if model override specified
        provider = None
        if args.model:
            from pageindex.llm.provider import LLMProvider
            from pageindex.llm.config import load_llm_config
            cfg = load_llm_config()
            cfg['tree_indexing_model'] = args.model
            provider = LLMProvider(cfg)

        # Process PDF file
        # Configure options
        opt = config(
            toc_check_page_num=args.toc_check_pages,
            max_page_num_each_node=args.max_pages_per_node,
            max_token_num_each_node=args.max_tokens_per_node,
            if_add_node_id=args.if_add_node_id,
            if_add_node_summary=args.if_add_node_summary,
            if_add_doc_description=args.if_add_doc_description,
            if_add_node_text=args.if_add_node_text
        )

        # Process the PDF
        toc_with_page_number = page_index_main(args.pdf_path, opt, provider=provider)
        print('Parsing done, saving to file...')

        # Save results
        pdf_name = os.path.splitext(os.path.basename(args.pdf_path))[0]
        output_dir = './results'
        output_file = f'{output_dir}/{pdf_name}_structure.json'
        os.makedirs(output_dir, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(toc_with_page_number, f, indent=2)

        print(f'Tree structure saved to: {output_file}')

    elif args.md_path:
        # Validate Markdown file
        if not args.md_path.lower().endswith(('.md', '.markdown')):
            raise ValueError("Markdown file must have .md or .markdown extension")
        if not os.path.isfile(args.md_path):
            raise ValueError(f"Markdown file not found: {args.md_path}")

        # Process markdown file
        print('Processing markdown file...')

        # Build provider if model override specified
        provider = None
        if args.model:
            from pageindex.llm.provider import LLMProvider
            from pageindex.llm.config import load_llm_config
            cfg = load_llm_config()
            cfg['tree_indexing_model'] = args.model
            provider = LLMProvider(cfg)

        # Use ConfigLoader to get consistent defaults (matching PDF behavior)
        config_loader = ConfigLoader()

        # Create options dict with user args
        user_opt = {
            'if_add_node_summary': args.if_add_node_summary,
            'if_add_doc_description': args.if_add_doc_description,
            'if_add_node_text': args.if_add_node_text,
            'if_add_node_id': args.if_add_node_id
        }

        # Load config with defaults from config.yaml
        opt = config_loader.load(user_opt)

        toc_with_page_number = asyncio.run(md_to_tree(
            md_path=args.md_path,
            if_thinning=args.if_thinning.lower() == 'yes',
            min_token_threshold=args.thinning_threshold,
            if_add_node_summary=opt.if_add_node_summary,
            summary_token_threshold=args.summary_token_threshold,
            model=args.model,
            if_add_doc_description=opt.if_add_doc_description,
            if_add_node_text=opt.if_add_node_text,
            if_add_node_id=opt.if_add_node_id,
            provider=provider
        ))

        print('Parsing done, saving to file...')

        # Save results
        md_name = os.path.splitext(os.path.basename(args.md_path))[0]
        output_dir = './results'
        output_file = f'{output_dir}/{md_name}_structure.json'
        os.makedirs(output_dir, exist_ok=True)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(toc_with_page_number, f, indent=2, ensure_ascii=False)

        print(f'Tree structure saved to: {output_file}')
